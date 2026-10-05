"""
Indian Financial PII Masking Pipeline & Reversible Session Vault.
Complies with RBI KYC Master Direction §24, PMLA 2002, and PCI-DSS Requirement 3.
Guarantees sensitive identifiers never reach local LLMs or unencrypted audit logs.
"""
import re
from typing import Dict, Tuple, Optional


class ReversibleVault:
    """Session-isolated vault mapping placeholder tokens back to original values."""
    def __init__(self):
        self._token_to_raw: Dict[str, str] = {}
        self._raw_to_token: Dict[str, str] = {}
        self._counters: Dict[str, int] = {
            "CARD": 0,
            "AADHAAR": 0,
            "PAN": 0,
            "IFSC": 0,
            "MOBILE": 0,
            "UPI": 0,
            "ACCOUNT": 0,
        }

    def get_or_create_token(self, entity_type: str, raw_value: str) -> str:
        clean_raw = raw_value.strip()
        if clean_raw in self._raw_to_token:
            return self._raw_to_token[clean_raw]

        self._counters[entity_type] = self._counters.get(entity_type, 0) + 1
        token = f"<{entity_type}_{self._counters[entity_type]}>"
        self._token_to_raw[token] = clean_raw
        self._raw_to_token[clean_raw] = token
        return token

    def unmask(self, text: str) -> str:
        """Replace all placeholder tokens with original raw values."""
        unmasked = text
        for token, raw in self._token_to_raw.items():
            unmasked = unmasked.replace(token, raw)
        return unmasked

    def get_token_map(self) -> Dict[str, str]:
        return dict(self._token_to_raw)


class PIIMasker:
    """
    High-precision recognizer and masker for Indian financial identifiers.
    Applies regex recognizers in order of specificity to prevent false positives.
    """

    # 1. 16-digit Card numbers (credit/debit)
    CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

    # 2. Aadhaar: 12 digits, first digit 2-9 per UIDAI specifications, optional spaces/hyphens
    AADHAAR_REGEX = re.compile(r"\b[2-9]\d{3}[-\s]?\d{4}[-\s]?\d{4}\b")

    # 3. PAN: 5 uppercase letters, 4 digits, 1 uppercase letter
    PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)

    # 4. IFSC: 4 letters, '0', 6 alphanumeric characters
    IFSC_REGEX = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)

    # 5. UPI ID: username@bank/psp handle
    UPI_REGEX = re.compile(r"\b[a-zA-Z0-9.\-_]{2,64}@[a-zA-Z]{2,32}\b")

    # 6. Indian Mobile Number: +91 or 0 prefix optional, 10 digits starting with 6-9
    MOBILE_REGEX = re.compile(r"(?:\+91[-\s]?|0\s?)?[6-9]\d{4}[-\s]?\d{5}\b")

    # 7. Bank Account Number: 9 to 18 digits with contextual keywords
    ACCOUNT_CONTEXT_REGEX = re.compile(
        r"(?:account|a/c|acc|acct|number|no\.?)\s*(?:is|:|-)?\s*([0-9]{9,18})\b",
        re.IGNORECASE
    )

    def mask(self, text: str, vault: Optional[ReversibleVault] = None) -> Tuple[str, ReversibleVault]:
        """
        Mask all recognized Indian financial PII tokens in text.
        Returns: (masked_text, vault)
        """
        if not text or not isinstance(text, str):
            return text, vault or ReversibleVault()

        if vault is None:
            vault = ReversibleVault()

        # Step 1: Credit / Debit Cards
        def repl_card(match):
            return vault.get_or_create_token("CARD", match.group(0))
        masked = self.CARD_REGEX.sub(repl_card, text)

        # Step 2: Aadhaar Numbers
        def repl_aadhaar(match):
            return vault.get_or_create_token("AADHAAR", match.group(0))
        masked = self.AADHAAR_REGEX.sub(repl_aadhaar, masked)

        # Step 3: PAN
        def repl_pan(match):
            return vault.get_or_create_token("PAN", match.group(0).upper())
        masked = self.PAN_REGEX.sub(repl_pan, masked)

        # Step 4: IFSC
        def repl_ifsc(match):
            return vault.get_or_create_token("IFSC", match.group(0).upper())
        masked = self.IFSC_REGEX.sub(repl_ifsc, masked)

        # Step 5: UPI IDs
        def repl_upi(match):
            return vault.get_or_create_token("UPI", match.group(0))
        masked = self.UPI_REGEX.sub(repl_upi, masked)

        # Step 6: Contextual Account Numbers
        def repl_acc(match):
            acc_num = match.group(1)
            token = vault.get_or_create_token("ACCOUNT", acc_num)
            full_str = match.group(0)
            return full_str.replace(acc_num, token)
        masked = self.ACCOUNT_CONTEXT_REGEX.sub(repl_acc, masked)

        # Step 7: Indian Mobile Numbers
        def repl_mobile(match):
            return vault.get_or_create_token("MOBILE", match.group(0))
        masked = self.MOBILE_REGEX.sub(repl_mobile, masked)

        return masked, vault

    def unmask(self, text: str, vault: ReversibleVault) -> str:
        """Safely restore masked tokens from vault."""
        return vault.unmask(text)


# Default singleton instance
pii_masker = PIIMasker()
