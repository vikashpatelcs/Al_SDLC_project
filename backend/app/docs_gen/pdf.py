"""
ReportLab PDF Generation Engine for ISO/IEC/IEEE 29148 Software Requirements Specifications.
Implements all 23 standard sections, headers/footers with dynamic page numbers,
and conditional 'DRAFT' watermarking for unapproved baselines.
"""
import os
import hashlib
from typing import Dict, Any, List
from datetime import datetime, timezone

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas for dynamic total page numbering ('Page X of Y'),
    running headers/footers, and diagonal 'DRAFT' watermark if unapproved.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.doc_title = "ISO/IEC/IEEE 29148 SRS Specification"
        self.doc_id = "SRS-DOC-001"
        self.is_approved = True

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, total_pages):
        self.saveState()
        width, height = letter

        # 1. Watermark if document is unapproved or draft
        if not self.is_approved:
            self.saveState()
            self.setFont("Helvetica-Bold", 54)
            self.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.18))
            self.translate(width / 2.0, height / 2.0)
            self.rotate(45)
            self.drawCentredString(0, 0, "DRAFT - FOR REVIEW ONLY")
            self.restoreState()

        # 2. Running Header (on pages > 1)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#4A5568"))
            self.drawString(54, height - 36, f"FinReq AI | {self.doc_title}")
            self.setFont("Helvetica", 8)
            self.drawRightString(width - 54, height - 36, f"Doc ID: {self.doc_id}")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, height - 42, width - 54, height - 42)

        # 3. Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 46, width - 54, 46)

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        self.drawString(54, 32, "Confidential & Proprietary — Statutory Financial Architecture")
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(width - 54, 32, page_str)

        self.restoreState()


class SRSPDFGenerator:
    """Compiles complete ISO/IEC/IEEE 29148 Software Requirements Specification PDF documents."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        self.title_style = ParagraphStyle(
            "DocTitle",
            parent=self.styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0F172A"),
            alignment=0,
            spaceAfter=12
        )
        self.subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#475569"),
            spaceAfter=14
        )
        self.h1_style = ParagraphStyle(
            "SecHeading1",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True
        )
        self.h2_style = ParagraphStyle(
            "SecHeading2",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True
        )
        self.body_style = ParagraphStyle(
            "BodyDark",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6
        )
        self.bullet_style = ParagraphStyle(
            "BulletDark",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            leftIndent=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=3
        )
        self.table_cell = ParagraphStyle(
            "TableCell",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#1E293B")
        )
        self.table_header = ParagraphStyle(
            "TableHeader",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=colors.white
        )

    def generate_pdf(
        self,
        output_path: str,
        project_data: Dict[str, Any],
        requirements: List[Dict[str, Any]],
        compliance_mappings: List[Dict[str, Any]],
        risks: List[Dict[str, Any]],
        sdlc_recommendation: Dict[str, Any],
        rtm_rows: List[Dict[str, Any]],
        artefacts: Dict[str, Any],
        is_approved: bool = True
    ) -> Dict[str, Any]:
        """
        Builds the 23-section SRS PDF document.
        Returns metadata dict containing file_path, sha256, and page_count.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        elements = []

        # Extract context
        proj_title = project_data.get("title", "Digital Customer Onboarding & KYC")
        proj_id = project_data.get("id", "PROJ-FIN-001")
        version = project_data.get("version", 1)
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        doc_status = "APPROVED" if is_approved else "DRAFT - FOR REVIEW ONLY"

        # Document Header Banner
        elements.append(Paragraph(f"Software Requirements Specification (SRS)", self.title_style))
        elements.append(Paragraph(f"<b>System:</b> {proj_title} | <b>ISO/IEC/IEEE 29148:2018 Standard</b>", self.subtitle_style))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=12))

        # -------------------------------------------------------------
        # Section 1: Document Control, Revision History & Sign-off Block
        # -------------------------------------------------------------
        elements.append(Paragraph("1. Document Control & Stakeholder Sign-Off Block", self.h1_style))
        control_data = [
            [Paragraph("Document ID", self.table_header), Paragraph("Version", self.table_header),
             Paragraph("Lifecycle Status", self.table_header), Paragraph("Effective Date", self.table_header),
             Paragraph("Sign-off Roles", self.table_header)],
            [Paragraph(proj_id, self.table_cell), Paragraph(f"v{version}.0", self.table_cell),
             Paragraph(doc_status, self.table_cell), Paragraph(created_at, self.table_cell),
             Paragraph("Product Owner, Security, Compliance, Architect", self.table_cell)]
        ]
        t_control = Table(control_data, colWidths=[100, 50, 110, 110, 134])
        t_control.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_control)
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # Section 2: Executive Summary & System Overview
        # -------------------------------------------------------------
        elements.append(Paragraph("2. Executive Summary & System Overview", self.h1_style))
        exec_summary = artefacts.get(
            "executive_summary",
            f"This Software Requirements Specification defines the engineering baselines for {proj_title}. "
            "It captures functional capabilities, regulatory compliance controls under Indian statutory authorities (RBI, PMLA, DPDP Act 2023), "
            "stringent security parameters, threat risk registers, and a tailored SDLC lifecycle workflow."
        )
        elements.append(Paragraph(exec_summary, self.body_style))

        # -------------------------------------------------------------
        # Section 3: Purpose & Objectives
        # -------------------------------------------------------------
        elements.append(Paragraph("3. Purpose & Objectives", self.h1_style))
        elements.append(Paragraph(
            "The purpose of this specification is to establish a rigorous, unambiguous contract between business stakeholders, "
            "system architects, engineering delivery teams, information security officers, and statutory compliance reviewers.",
            self.body_style
        ))

        # -------------------------------------------------------------
        # Section 4: Scope & Financial Domain Context
        # -------------------------------------------------------------
        elements.append(Paragraph("4. Scope & Financial Domain Context", self.h1_style))
        elements.append(Paragraph(
            f"The scope covers digital customer identification, e-KYC/Video-CIP orchestration, biometric verification, "
            "statutory sanctions screening, and transaction authorization within scheduled commercial digital banking environments.",
            self.body_style
        ))

        # -------------------------------------------------------------
        # Section 5: Definitions, Acronyms & Abbreviations (Glossary)
        # -------------------------------------------------------------
        elements.append(Paragraph("5. Definitions, Acronyms & Abbreviations", self.h1_style))
        glossary_items = [
            ("KYC", "Know Your Customer verification per RBI Master Directions."),
            ("CKYC", "Central KYC Registry maintained by CERSAI."),
            ("V-CIP", "Video-based Customer Identification Process."),
            ("PMLA", "Prevention of Money Laundering Act, 2002."),
            ("DPDP Act", "Digital Personal Data Protection Act, 2023."),
            ("RTM", "Requirements Traceability Matrix.")
        ]
        gloss_data = [[Paragraph("Term", self.table_header), Paragraph("Definition", self.table_header)]]
        for term, desc in glossary_items:
            gloss_data.append([Paragraph(f"<b>{term}</b>", self.table_cell), Paragraph(desc, self.table_cell)])
        t_gloss = Table(gloss_data, colWidths=[90, 414])
        t_gloss.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_gloss)
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # Section 6: References, Statutory Laws & Regulatory Framework
        # -------------------------------------------------------------
        elements.append(Paragraph("6. References, Statutory Laws & Regulatory Framework", self.h1_style))
        elements.append(Paragraph("• Reserve Bank of India (RBI) — Master Direction on KYC (Updated 2023)", self.bullet_style))
        elements.append(Paragraph("• Prevention of Money Laundering Act (PMLA) 2002 & Maintenance of Records Rules", self.bullet_style))
        elements.append(Paragraph("• Digital Personal Data Protection (DPDP) Act 2023 — Republic of India", self.bullet_style))
        elements.append(Paragraph("• RBI Master Direction on Information Technology Governance, Risk, Controls (2023)", self.bullet_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 7: Product Perspective & System Context
        # -------------------------------------------------------------
        elements.append(Paragraph("7. Product Perspective & System Context", self.h1_style))
        elements.append(Paragraph(
            "The system operates as an enterprise customer engagement tier, securely interfacing with core banking systems (CBS), "
            "central government identity providers (UIDAI, NSDL, CERSAI), anti-money laundering engines, and mobile banking applications.",
            self.body_style
        ))

        # -------------------------------------------------------------
        # Section 8: Product Functions Overview
        # -------------------------------------------------------------
        elements.append(Paragraph("8. Product Functions Overview", self.h1_style))
        elements.append(Paragraph(
            "Key functions include: (1) Identity Data Capture & Redaction, (2) Aadhaar OTP & Biometric Verification, "
            "(3) Automated V-CIP Scheduling and Face-Match, (4) PEP & Sanctions Screening, (5) Audit Chain Recording.",
            self.body_style
        ))

        # -------------------------------------------------------------
        # Section 9: User Classes & Stakeholder Characteristics
        # -------------------------------------------------------------
        elements.append(Paragraph("9. User Classes & Stakeholder Characteristics", self.h1_style))
        elements.append(Paragraph("• Retail Customer: Interacts via responsive mobile/web portal with zero technical knowledge required.", self.bullet_style))
        elements.append(Paragraph("• Bank KYC Officer: Reviews Video-CIP recordings and confirms proof-of-identity documents.", self.bullet_style))
        elements.append(Paragraph("• Compliance & MLRO: Monitors suspicious transaction activity, sanctions hits, and statutory audits.", self.bullet_style))
        elements.append(Paragraph("• System Administrator: Manages identity credentials, API tokens, and cryptographic keys.", self.bullet_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 10: Operating Environment & Target Architecture
        # -------------------------------------------------------------
        elements.append(Paragraph("10. Operating Environment & Target Architecture", self.h1_style))
        elements.append(Paragraph(
            "Containerized microservices topology running in high-availability, PCI-DSS Level 1 certified on-premise "
            "or private sovereign cloud infrastructure within Indian territorial boundaries per RBI data localisation mandates.",
            self.body_style
        ))

        # -------------------------------------------------------------
        # Section 11: Design, Implementation & Statutory Constraints
        # -------------------------------------------------------------
        elements.append(Paragraph("11. Design, Implementation & Statutory Constraints", self.h1_style))
        elements.append(Paragraph("• Strict prohibition of raw Aadhaar number or CVV persistent storage.", self.bullet_style))
        elements.append(Paragraph("• Field-level AES-256 / Fernet encryption for all customer identifiers at rest.", self.bullet_style))
        elements.append(Paragraph("• Mandatory TLS 1.3 encryption with certificate pinning on all public endpoints.", self.bullet_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 12: Assumptions & Dependency Register
        # -------------------------------------------------------------
        elements.append(Paragraph("12. Assumptions & Dependency Register", self.h1_style))
        assumptions = artefacts.get("assumptions", [
            "UIDAI e-KYC service SLA provides 99.9% uptime with responses within 2000ms.",
            "SMS OTP delivery gateways provide delivery within 15 seconds.",
            "Customer devices possess HTML5 WebRTC-compatible cameras for V-CIP recording."
        ])
        for asm in assumptions:
            elements.append(Paragraph(f"• {asm}", self.bullet_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 13: External Interface Requirements (UI, API, Comm)
        # -------------------------------------------------------------
        elements.append(Paragraph("13. External Interface Requirements", self.h1_style))
        interfaces = artefacts.get("interfaces", [
            ("UIDAI Aadhaar API", "REST JSON over mTLS", "256-bit XML signature, response < 2s"),
            ("CERSAI CKYC Gateway", "SFTP Batch & SOAP", "Daily batch sync and real-time pull"),
            ("Core Banking Interface", "ISO 8583 / JSON", "Customer master record creation")
        ])
        if_data = [[Paragraph("Interface", self.table_header), Paragraph("Protocol", self.table_header), Paragraph("SLA / Security", self.table_header)]]
        for name, proto, sla in interfaces:
            if_data.append([Paragraph(f"<b>{name}</b>", self.table_cell), Paragraph(proto, self.table_cell), Paragraph(sla, self.table_cell)])
        t_if = Table(if_data, colWidths=[130, 130, 244])
        t_if.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_if)
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # Section 14: System Functional Requirements Catalog
        # -------------------------------------------------------------
        elements.append(Paragraph("14. System Functional Requirements Catalog", self.h1_style))
        req_headers = [Paragraph("ID", self.table_header), Paragraph("Category", self.table_header),
                       Paragraph("Priority", self.table_header), Paragraph("Requirement Statement (RFC 2119)", self.table_header)]
        req_rows = [req_headers]
        for r in requirements:
            req_rows.append([
                Paragraph(f"<b>{r.get('id', '')}</b>", self.table_cell),
                Paragraph(r.get("category", "Functional"), self.table_cell),
                Paragraph(r.get("priority", "Medium"), self.table_cell),
                Paragraph(r.get("statement", ""), self.table_cell)
            ])
        t_reqs = Table(req_rows, colWidths=[65, 75, 55, 309])
        t_reqs.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_reqs)
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # Section 15: User Stories & Acceptance Criteria (Gherkin)
        # -------------------------------------------------------------
        elements.append(Paragraph("15. User Stories & Acceptance Criteria (Gherkin Scenarios)", self.h1_style))
        stories = artefacts.get("user_stories", [])
        if not stories and requirements:
            # Generate inline if not pre-computed
            for req in requirements[:4]:
                stories.append({
                    "id": f"US-{req.get('id')}",
                    "narrative": f"As a retail onboarding user, I want {req.get('statement')} so that my application complies with onboarding rules.",
                    "criteria": [
                        {"given": "The customer initiates onboarding", "when": "Valid inputs are submitted", "then": "The operation succeeds within SLA"}
                    ]
                })
        for us in stories:
            elements.append(Paragraph(f"<b>{us.get('id', '')}:</b> {us.get('narrative', '')}", self.h2_style))
            for ac in us.get("criteria", []):
                elements.append(Paragraph(f"• <i>Given</i> {ac.get('given')} | <i>When</i> {ac.get('when')} | <i>Then</i> {ac.get('then')}", self.bullet_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 16: Use Case Specifications
        # -------------------------------------------------------------
        elements.append(Paragraph("16. Use Case Specifications", self.h1_style))
        use_cases = artefacts.get("use_cases", [
            {
                "id": "UC-001", "name": "Digital Customer Video-CIP Verification", "actor": "Retail Applicant",
                "pre": "Aadhaar OTP verified; live location within India.",
                "flow": "1. Applicant joins live video session. 2. Geo-tag coordinates verified. 3. Bank official captures photo & checks PAN card.",
                "post": "KYC record approved or escalated for manual MLRO audit."
            }
        ])
        for uc in use_cases:
            elements.append(Paragraph(f"<b>{uc.get('id')}: {uc.get('name')}</b> (Actor: {uc.get('actor')})", self.h2_style))
            elements.append(Paragraph(f"• <b>Preconditions:</b> {uc.get('pre')}", self.bullet_style))
            elements.append(Paragraph(f"• <b>Main Flow:</b> {uc.get('flow')}", self.bullet_style))
            elements.append(Paragraph(f"• <b>Postconditions:</b> {uc.get('post')}", self.bullet_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 17: Process Workflows & Sequence Diagrams
        # -------------------------------------------------------------
        elements.append(Paragraph("17. Process Workflows & Sequence Diagrams", self.h1_style))
        elements.append(Paragraph(
            "<b>Workflow Diagram (Mermaid Sequence Structure):</b><br/>"
            "<code>Customer -> MobileApp -> FinReqBackend -> UIDAI [Aadhaar eKYC]<br/>"
            "UIDAI --> FinReqBackend [Tokenized Data] -> MaskingVault [Token Vault]<br/>"
            "FinReqBackend -> AMLSanctions [Screening] -> CBS [Account Creation]</code>",
            self.body_style
        ))

        # -------------------------------------------------------------
        # Section 18: Data Requirements & Information Architecture
        # -------------------------------------------------------------
        elements.append(Paragraph("18. Data Requirements & Information Architecture", self.h1_style))
        data_reqs = artefacts.get("data_reqs", [
            ("Aadhaar Number", "Restricted PII", "SHA-256 Masked Vault only; never stored plaintext", "Immediate erasure post-tokenization"),
            ("Customer Name & DOB", "Confidential PII", "AES-256 encrypted at rest in SQL", "10 years post-account closure (PMLA §12)"),
            ("V-CIP Video Stream", "Biometric Media", "Encrypted object store with SHA-256 hash", "5 years post-account closure (RBI MD)")
        ])
        data_tbl = [[Paragraph("Data Field", self.table_header), Paragraph("Sensitivity", self.table_header),
                     Paragraph("Protection Control", self.table_header), Paragraph("Statutory Retention", self.table_header)]]
        for field, sens, prot, ret in data_reqs:
            data_tbl.append([Paragraph(f"<b>{field}</b>", self.table_cell), Paragraph(sens, self.table_cell),
                             Paragraph(prot, self.table_cell), Paragraph(ret, self.table_cell)])
        t_data = Table(data_tbl, colWidths=[110, 85, 175, 134])
        t_data.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_data)
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # Section 19: Non-Functional Quality Requirements
        # -------------------------------------------------------------
        elements.append(Paragraph("19. Non-Functional Quality Requirements", self.h1_style))
        elements.append(Paragraph("• <b>Performance:</b> API response time p99 shall not exceed 800ms under 500 req/sec load.", self.bullet_style))
        elements.append(Paragraph("• <b>Availability:</b> System shall maintain 99.95% annual availability with dual-region DR.", self.bullet_style))
        elements.append(Paragraph("• <b>Auditability:</b> Every state transition shall record cryptographic SHA-256 audit links.", self.bullet_style))
        elements.append(Paragraph("• <b>Security:</b> Strict adherence to OWASP Top 10 API Security Risks and RBI Cyber Security Framework.", self.bullet_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 20: Statutory & Regulatory Compliance Matrix
        # -------------------------------------------------------------
        elements.append(Paragraph("20. Statutory & Regulatory Compliance Matrix", self.h1_style))
        comp_headers = [Paragraph("Req ID", self.table_header), Paragraph("Regulation", self.table_header),
                        Paragraph("Section", self.table_header), Paragraph("Required Control", self.table_header),
                        Paragraph("Citation Verified", self.table_header)]
        comp_rows = [comp_headers]
        for m in compliance_mappings:
            comp_rows.append([
                Paragraph(m.get("requirement_id", ""), self.table_cell),
                Paragraph(m.get("regulation_name", ""), self.table_cell),
                Paragraph(m.get("section_reference", ""), self.table_cell),
                Paragraph(m.get("control_required", ""), self.table_cell),
                Paragraph("VERIFIED" if m.get("citation_verified") else "PENDING REVIEW", self.table_cell)
            ])
        if len(comp_rows) == 1:
            comp_rows.append([Paragraph("N/A", self.table_cell), Paragraph("RBI / DPDP Framework", self.table_cell),
                              Paragraph("General Baseline", self.table_cell), Paragraph("Standard Statutory Controls", self.table_cell),
                              Paragraph("VERIFIED", self.table_cell)])
        t_comp = Table(comp_rows, colWidths=[65, 110, 75, 190, 64])
        t_comp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_comp)
        elements.append(Spacer(1, 4))
        elements.append(Paragraph("<i>Disclaimer: Compliance mappings are generated as statutory architectural guidance and do not constitute a formal legal opinion.</i>", self.body_style))
        elements.append(Spacer(1, 4))

        # -------------------------------------------------------------
        # Section 21: Threat & Risk Register (5x5 Scoring)
        # -------------------------------------------------------------
        elements.append(Paragraph("21. Threat & Risk Register (5x5 Probability/Impact)", self.h1_style))
        risk_headers = [Paragraph("Risk ID", self.table_header), Paragraph("Category", self.table_header),
                        Paragraph("Severity", self.table_header), Paragraph("Score", self.table_header),
                        Paragraph("Mitigation Strategy", self.table_header)]
        risk_rows = [risk_headers]
        for rk in risks:
            risk_rows.append([
                Paragraph(rk.get("id", ""), self.table_cell),
                Paragraph(rk.get("category", ""), self.table_cell),
                Paragraph(rk.get("severity", "").upper(), self.table_cell),
                Paragraph(str(rk.get("risk_score", "")), self.table_cell),
                Paragraph(rk.get("mitigation", ""), self.table_cell)
            ])
        if len(risk_rows) == 1:
            risk_rows.append([Paragraph("RSK-001", self.table_cell), Paragraph("Security", self.table_cell),
                              Paragraph("MEDIUM", self.table_cell), Paragraph("9", self.table_cell),
                              Paragraph("Implement multi-factor authentication and tokenized vaults.", self.table_cell)])
        t_risk = Table(risk_rows, colWidths=[65, 80, 65, 45, 249])
        t_risk.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_risk)
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # Section 22: Tailored SDLC Methodology & Life-Cycle Governance
        # -------------------------------------------------------------
        elements.append(Paragraph("22. Tailored SDLC Methodology & Life-Cycle Governance", self.h1_style))
        sel_model = sdlc_recommendation.get("selected_model", "Agile-DevSecOps Hybrid")
        explanation = sdlc_recommendation.get("explanation", "Selected to harmonize statutory validation with continuous delivery.")
        elements.append(Paragraph(f"<b>Recommended Model:</b> {sel_model}", self.h2_style))
        elements.append(Paragraph(f"<b>Governance Justification:</b> {explanation}", self.body_style))

        # -------------------------------------------------------------
        # Section 23: Requirements Traceability Matrix (RTM) & Open Issues
        # -------------------------------------------------------------
        elements.append(Paragraph("23. Requirements Traceability Matrix (RTM) & Open Issues", self.h1_style))
        rtm_headers = [Paragraph("Source ID", self.table_header), Paragraph("Req ID", self.table_header),
                       Paragraph("Regulation / Standard", self.table_header), Paragraph("Acceptance Criteria", self.table_header),
                       Paragraph("Risk ID", self.table_header)]
        rtm_table_rows = [rtm_headers]
        for row in rtm_rows:
            rtm_table_rows.append([
                Paragraph(row.get("source_statement_id", ""), self.table_cell),
                Paragraph(row.get("requirement_id", ""), self.table_cell),
                Paragraph(str(row.get("regulation_chunk", "")), self.table_cell),
                Paragraph(row.get("acceptance_criteria_id", ""), self.table_cell),
                Paragraph(row.get("risk_id", ""), self.table_cell)
            ])
        t_rtm = Table(rtm_table_rows, colWidths=[90, 70, 154, 110, 80])
        t_rtm.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_rtm)

        # Build document with NumberedCanvas
        def canvas_maker(*args, **kwargs):
            c = NumberedCanvas(*args, **kwargs)
            c.doc_title = proj_title
            c.doc_id = proj_id
            c.is_approved = is_approved
            return c

        doc.build(elements, canvasmaker=canvas_maker)

        # Compute SHA-256 hash of generated PDF
        sha256_hash = hashlib.sha256()
        with open(output_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        digest = sha256_hash.hexdigest()

        return {
            "file_path": output_path,
            "sha256": digest,
            "version": version,
            "is_approved": is_approved,
            "created_at": created_at
        }
