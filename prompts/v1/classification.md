# Multi-Label Requirement Classification Prompt (v1)

Classify the input financial requirement statement across the 13 canonical categories from Problem Statement §9:
- Business
- Functional
- Non-Functional
- Technical
- Security
- Privacy
- Compliance
- Performance
- Availability
- Auditability
- Operational
- Interface
- Data

Output Format:
Output a single JSON object:
```json
{
  "primary_category": "Security",
  "secondary_categories": ["Compliance", "Privacy"],
  "confidence": 0.95,
  "rationale": "Requirement enforces cryptographic storage of PAN in compliance with PCI-DSS."
}
```
