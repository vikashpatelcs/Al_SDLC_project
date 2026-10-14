"""
Coordinator Agent for Phase 9: Multi-Agent Orchestration.
The Coordinator is the central orchestrator and the single authoritative persistence writer (Rule 7).
It drives the LangGraph state machine, logs agent executions to `agent_executions`, and manages DB transactions.
"""
import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.core.permissions import assert_can_write_db
from backend.app.db.models import (
    Chat,
    Project,
    RequirementModel,
    RequirementVersion,
    Assumption,
    RequirementIssueModel,
    AgentExecutionModel,
    ComplianceMappingModel,
    RiskModel,
    SDLCRecommendationModel,
    GeneratedDocumentModel,
    TraceabilityModel,
)
from backend.app.graph.state import AgentState, ConversationPhase
from backend.app.graph.workflow import build_orchestration_graph
from backend.app.graph.checkpointer import SqliteCheckpointer
from backend.app.core.audit import record_audit_event, AuditEventType
from backend.app.schemas.sdlc import SDLCModelType
from backend.app.agents.sdlc import sdlc_agent
from backend.app.agents.documentation import DocumentationAgent


class CoordinatorAgent:
    def __init__(self, checkpointer: Optional[SqliteCheckpointer] = None):
        self.checkpointer = checkpointer or SqliteCheckpointer()
        self.graph = build_orchestration_graph(checkpointer=self.checkpointer)

    def _is_sdlc_intent(self, text: str) -> bool:
        clean = text.lower().strip()
        sdlc_keywords = [
            "sdlc", "methodology", "waterfall", "v-model", "vmodel", "agile", "devsecops", "spiral", "lifecycle"
        ]
        action_keywords = [
            "change", "switch", "challenge", "adjust", "update", "select", "use", "prefer", "want", "apply", "set", "why", "explain", "reason"
        ]
        if any(k in clean for k in ["change sdlc", "switch sdlc", "challenge sdlc", "adjust factor", "sdlc methodology", "select sdlc", "update sdlc", "explain sdlc", "why sdlc", "what sdlc"]):
            return True
        if any(k in clean for k in sdlc_keywords) and any(a in clean for a in action_keywords):
            return True
        if any(a in clean for a in [
            "[action selected: adjust decision factors]",
            "[action selected: switch to",
            "[action selected: adopt recommendation]",
            "[action selected: export workflow]"
        ]):
            return True
        if clean in ["waterfall", "v-model", "vmodel", "agile", "devsecops", "spiral", "sdlc"]:
            return True
        return False

    def _parse_target_model(self, text: str) -> Optional[SDLCModelType]:
        clean = text.lower()
        if "waterfall" in clean:
            return SDLCModelType.WATERFALL
        if "v-model" in clean or "vmodel" in clean:
            if "agile" in clean or "hybrid" in clean:
                return SDLCModelType.AGILE_V_MODEL
            return SDLCModelType.V_MODEL
        if "devsecops" in clean:
            if "pure" in clean or "standalone" in clean:
                return SDLCModelType.DEVSECOPS
            return SDLCModelType.AGILE_DEVSECOPS
        if "spiral" in clean:
            return SDLCModelType.SPIRAL
        if "agile" in clean or "scrum" in clean:
            return SDLCModelType.AGILE
        return None

    def _is_requirement_edit_intent(self, text: str) -> bool:
        clean = text.lower().strip()
        if any(p in clean for p in [
            "change requirement", "update requirement", "modify requirement", "add requirement",
            "edit requirement", "delete requirement", "remove requirement", "new requirement"
        ]):
            return True
        if re.search(r'\breq-[a-z0-9\-]+\b', clean) and any(w in clean for w in ["change", "update", "modify", "replace", "set"]):
            return True
        return False

    def _handle_requirement_edit(
        self,
        db: Session,
        chat: Chat,
        project: Project,
        user_text: str
    ) -> Dict[str, Any]:
        """Handles user requests to add, modify, or update specifications post-baselining."""
        start_time = time.time()
        progress = [
            "Parsing specification modification request...",
            "Applying updates and versioning requirement history...",
            "Re-evaluating SDLC compatibility against modified statutory constraints..."
        ]

        existing_reqs = db.query(RequirementModel).filter(RequirementModel.project_id == project.id).all()
        clean = user_text.strip()
        match_id = re.search(r'\b(REQ-[A-Za-z0-9\-]+)\b', clean, re.IGNORECASE)

        updated_req_id = None
        action_note = ""

        if match_id:
            req_id_raw = match_id.group(1).upper()
            target_req = next((r for r in existing_reqs if r.id.upper() == req_id_raw), None)
            if target_req:
                # Extract new statement text after colon or 'to'
                new_stmt = clean
                if ":" in clean:
                    new_stmt = clean.split(":", 1)[1].strip()
                elif " to " in clean.lower():
                    new_stmt = clean.lower().split(" to ", 1)[1].strip()
                if not new_stmt.lower().startswith("the system shall"):
                    new_stmt = f"The system shall {new_stmt[0].lower() + new_stmt[1:]}"
                if not new_stmt.endswith("."):
                    new_stmt += "."

                target_req.statement = new_stmt
                target_req.version = (target_req.version or 1) + 1
                updated_req_id = target_req.id
                db.flush()

                # Add new version entry
                ver_model = RequirementVersion(
                    id=str(uuid.uuid4()),
                    requirement_id=target_req.id,
                    version=target_req.version,
                    statement=target_req.statement,
                    category=target_req.category,
                    priority=target_req.priority,
                    status=target_req.status,
                    changed_by="Stakeholder (Chat)",
                    change_reason="Direct update requested via chat"
                )
                db.add(ver_model)
                action_note = f"Updated **{target_req.id}** to: *\"{target_req.statement}\"*"
        
        if not updated_req_id:
            # Add as new requirement
            new_stmt = clean
            for prefix in ["add requirement:", "add requirement", "new requirement:", "new requirement"]:
                if new_stmt.lower().startswith(prefix):
                    new_stmt = new_stmt[len(prefix):].strip()
            if not new_stmt.lower().startswith("the system shall"):
                new_stmt = f"The system shall {new_stmt[0].lower() + new_stmt[1:]}"
            if not new_stmt.endswith("."):
                new_stmt += "."

            seq = len(existing_reqs) + 1
            new_id = f"REQ-CUS-{project.id[:4].upper()}-{seq:03d}"
            new_rm = RequirementModel(
                id=new_id,
                project_id=project.id,
                statement=new_stmt,
                category="Functional",
                priority="High",
                version=1,
                status="approved",
                source_statement_id=f"chat#{chat.id[:6]}",
                business_justification="Added per user request in chat"
            )
            db.add(new_rm)
            db.flush()
            ver_model = RequirementVersion(
                id=str(uuid.uuid4()),
                requirement_id=new_id,
                version=1,
                statement=new_stmt,
                category="Functional",
                priority="High",
                status="approved",
                changed_by="Stakeholder (Chat)",
                change_reason="Added via chat request"
            )
            db.add(ver_model)
            updated_req_id = new_id
            action_note = f"Added new specification **{new_id}**: *\"{new_stmt}\"*"

        db.commit()
        existing_reqs = db.query(RequirementModel).filter(RequirementModel.project_id == project.id).all()

        # Re-compute SDLC recommendation
        rec = sdlc_agent.recommend_sdlc(
            requirements=existing_reqs,
            project_id=project.id,
            chat_id=chat.id
        )

        # Update SDLC in DB
        rec_row = db.query(SDLCRecommendationModel).filter(SDLCRecommendationModel.project_id == project.id).first()
        if rec_row:
            rec_row.selected_model = rec.selected_model.value
            rec_row.rankings_json = json.dumps([r.model_dump(mode="json") for r in rec.rankings])
            rec_row.factors_json = json.dumps({k: v.model_dump(mode="json") for k, v in rec.factor_evaluations.items()})
            rec_row.explanation = rec.explanation
            rec_row.workflow_json = json.dumps([p.model_dump(mode="json") for p in rec.workflow])
            db.commit()

        # Recompile SRS PDF
        progress.append("Re-compiling IEEE 29148 SRS specification package...")
        doc_agent = DocumentationAgent()
        req_dicts = [
            {"id": r.id, "statement": r.statement, "category": r.category, "priority": r.priority, "status": "approved"}
            for r in existing_reqs
        ]
        comp_maps = [
            {"id": m.id, "requirement_id": m.requirement_id, "regulation_name": m.regulation_name,
             "section_reference": m.section_reference, "citation_quote": m.citation_quote,
             "citation_verified": m.citation_verified, "control_required": m.control_required}
            for m in db.query(ComplianceMappingModel).filter(ComplianceMappingModel.project_id == project.id).all()
        ]
        risks = [
            {"id": rk.id, "title": rk.title, "category": rk.category, "probability": rk.probability,
             "impact": rk.impact, "risk_score": rk.risk_score, "severity": rk.severity, "mitigation": rk.mitigation}
            for rk in db.query(RiskModel).filter(RiskModel.project_id == project.id).all()
        ]
        doc_res = doc_agent.compile_srs(
            db=db,
            chat_id=chat.id,
            project_data={"id": project.id, "title": project.title or chat.title, "version": 1},
            requirements=req_dicts,
            compliance_mappings=comp_maps,
            risks=risks,
            sdlc_recommendation=rec.model_dump(mode="json"),
            is_approved=True
        )

        sdlc_card = sdlc_agent.build_sdlc_ranking_card(rec)
        pdf_card = doc_res["action_card"]

        response_text = (
            f"### ✏️ Specification Updated Successfully\n\n"
            f"{action_note}\n\n"
            f"**Current Baseline:** {len(existing_reqs)} Active Requirements | RTM Coverage: {int(doc_res['coverage_score'] * 100)}%\n\n"
            f"---\n"
            f"{rec.explanation}\n\n"
            f"---\n"
            f"📄 **Updated IEEE 29148 SRS Package Available Below**"
        )

        return {
            "chat_id": chat.id,
            "project_id": project.id,
            "phase": ConversationPhase.DONE.value,
            "requirements": [r.statement for r in existing_reqs],
            "action_cards": [sdlc_card.model_dump(mode="json"), pdf_card.model_dump(mode="json")],
            "progress_messages": progress,
            "response_text": response_text
        }

    def _handle_sdlc_challenge(
        self,
        db: Session,
        chat: Chat,
        project: Project,
        user_text: str
    ) -> Dict[str, Any]:
        """
        Handles interactive SDLC methodology changes, factor overrides, and challenges per PS §13-§15.
        Re-scores compatibility, explains trade-offs, updates the database, and re-compiles the SRS PDF.
        """
        start_time = time.time()
        progress = [
            "Analyzing SDLC methodology challenge against statutory financial constraints...",
            "Computing multi-criteria decision compatibility (MCDA) across project factors..."
        ]

        # 1. Fetch project requirements (or load standard banking defaults if none exist)
        existing_reqs = db.query(RequirementModel).filter(RequirementModel.project_id == project.id).all()
        if not existing_reqs:
            from backend.app.agents.requirement_engineer import requirement_engineer_agent
            std_text = (
                "The system shall verify customer identity using UIDAI Aadhaar offline XML verification. "
                "The system shall validate customer PAN validity against NSDL database prior to activation. "
                "The system shall encrypt all customer KYC documents at rest using AES-256 field-level encryption. "
                "The system shall retain all audit logs and customer records for five years in accordance with PMLA 2002. "
                "The system shall perform biometric liveness detection and facial matching during video KYC onboarding. "
                "The system shall enforce role-based access control and multi-factor authentication for banking back-office personnel."
            )
            extracted = requirement_engineer_agent.extract_requirements_from_text(
                text=std_text,
                source_statement_id=f"seed#{project.id[:6]}",
                project_id=project.id
            )
            for r in extracted:
                rm = RequirementModel(
                    id=r.id, project_id=project.id, statement=r.statement,
                    category=r.category.value, priority=r.priority.value, version=1, status="approved"
                )
                db.add(rm)
            db.flush()
            existing_reqs = db.query(RequirementModel).filter(RequirementModel.project_id == project.id).all()

        # 2. Compute SDLC recommendation on existing requirements
        rec = sdlc_agent.recommend_sdlc(
            requirements=existing_reqs,
            project_id=project.id,
            chat_id=chat.id
        )

        target_model = self._parse_target_model(user_text)

        # 3. Model Switch Logic
        if target_model:
            target_rank = next((r for r in rec.rankings if r.model_type == target_model), None)
            top_rank = rec.rankings[0]

            rec.selected_model = target_model
            rec.workflow = sdlc_agent.generate_customized_workflow(target_model, existing_reqs)

            tradeoff_text = {
                SDLCModelType.WATERFALL: (
                    "⚠️ **Statutory & Operational Trade-offs for Waterfall:**\n"
                    "• **Sequential Regulatory Verification:** Waterfall provides strict formal documentation gates suitable for static audits, but cannot accommodate frequent regulatory amendments (RBI Master Directions/PMLA circular updates) without extensive rework.\n"
                    "• **Late Security Discovery:** Security and vulnerability testing occur in late phases rather than continuously via automated CI/CD pipelines, increasing defect remediation costs."
                ),
                SDLCModelType.AGILE: (
                    "⚠️ **Statutory & Operational Trade-offs for Pure Agile:**\n"
                    "• **Compliance Gate Deficit:** Pure Agile lacks the mandatory formal compliance hold gates required by RBI Master Directions.\n"
                    "• **Audit Trail Vulnerability:** High sprint velocity risks sparse formal compliance sign-offs unless supplemented by DevSecOps automation."
                ),
                SDLCModelType.V_MODEL: (
                    "ℹ️ **Characteristics of V-Model (Regulated Hybrid):**\n"
                    "• **Rigorous Verification:** Excellent bilateral verification pairing requirements directly with validation test suites, ideal for core banking switches.\n"
                    "• **Delivery Cadence:** Longer release cycles compared to automated continuous delivery pipelines."
                ),
                SDLCModelType.AGILE_DEVSECOPS: (
                    "✅ **Characteristics of Agile + DevSecOps Hybrid:**\n"
                    "• **Statutory & Speed Balance:** Integrates rapid sprint iterations with automated SAST/DAST/SCA security gates, automated compliance checks, and continuous audit logging."
                ),
                SDLCModelType.AGILE_V_MODEL: (
                    "ℹ️ **Characteristics of Agile + V-Model Hybrid:**\n"
                    "• **Sprint-Level Verification:** Combines bilateral testing verification matrices with 2-week iterations, suitable for mission-critical banking components."
                ),
                SDLCModelType.DEVSECOPS: (
                    "✅ **Characteristics of Automated DevSecOps:**\n"
                    "• **Continuous Compliance & Deployment:** Real-time pipeline verification with automated security scanning on every commit."
                ),
                SDLCModelType.SPIRAL: (
                    "ℹ️ **Characteristics of Spiral (Risk-Driven):**\n"
                    "• **High-Risk Exploration:** Emphasizes iterative prototyping and formal risk assessment cycles before major commitments."
                ),
            }.get(target_model, "Custom lifecycle model applied.")

            # Update DB recommendation record
            rec_row = db.query(SDLCRecommendationModel).filter(SDLCRecommendationModel.project_id == project.id).first()
            if not rec_row:
                rec_row = SDLCRecommendationModel(
                    id=str(uuid.uuid4()),
                    project_id=project.id,
                    chat_id=chat.id,
                    selected_model=target_model.value,
                    rankings_json=json.dumps([r.model_dump(mode="json") for r in rec.rankings]),
                    factors_json=json.dumps({k: v.model_dump(mode="json") for k, v in rec.factor_evaluations.items()}),
                    explanation=rec.explanation,
                    workflow_json=json.dumps([p.model_dump(mode="json") for p in rec.workflow]),
                    is_approved=True
                )
                db.add(rec_row)
            else:
                rec_row.selected_model = target_model.value
                rec_row.workflow_json = json.dumps([p.model_dump(mode="json") for p in rec.workflow])
                rec_row.is_approved = True
            db.flush()

            # Recompile SRS PDF
            progress.append(f"Re-compiling ISO/IEC/IEEE 29148 SRS document with {target_model.value} workflow...")
            doc_agent = DocumentationAgent()
            req_dicts = [
                {"id": r.id, "statement": r.statement, "category": r.category, "priority": r.priority, "status": "approved"}
                for r in existing_reqs
            ]
            comp_maps = [
                {"id": m.id, "requirement_id": m.requirement_id, "regulation_name": m.regulation_name,
                 "section_reference": m.section_reference, "citation_quote": m.citation_quote,
                 "citation_verified": m.citation_verified, "control_required": m.control_required}
                for m in db.query(ComplianceMappingModel).filter(ComplianceMappingModel.project_id == project.id).all()
            ]
            risks = [
                {"id": rk.id, "title": rk.title, "category": rk.category, "probability": rk.probability,
                 "impact": rk.impact, "risk_score": rk.risk_score, "severity": rk.severity, "mitigation": rk.mitigation}
                for rk in db.query(RiskModel).filter(RiskModel.project_id == project.id).all()
            ]
            doc_res = doc_agent.compile_srs(
                db=db,
                chat_id=chat.id,
                project_data={"id": project.id, "title": project.title or chat.title, "version": 1},
                requirements=req_dicts,
                compliance_mappings=comp_maps,
                risks=risks,
                sdlc_recommendation=rec.model_dump(mode="json"),
                is_approved=True
            )

            # Build cards
            sdlc_card = sdlc_agent.build_sdlc_ranking_card(rec)
            sdlc_card.actions = ["Switch to Agile + DevSecOps", "Switch to Waterfall", "Switch to V-Model", "Switch to Agile"]
            pdf_card = doc_res["action_card"]

            target_pct = f"{target_rank.score_percentage:.1f}%" if target_rank else "60.0%"
            target_rk = f"#{target_rank.rank}" if target_rank else "N/A"
            top_pct = f"{top_rank.score_percentage:.1f}%"

            response_text = (
                f"### 🔄 SDLC Methodology Updated: **{target_model.value}**\n\n"
                f"Per your instruction, the project engineering lifecycle has been switched to **{target_model.value}**.\n\n"
                f"**MCDA Compatibility Assessment (Evaluated from {len(existing_reqs)} Requirements):**\n"
                f"• **Selected Model Score:** **{target_pct}** (Ranked {target_rk} of 7)\n"
                f"• **Top Algorithmic Fit:** **{top_rank.model_type.value}** ({top_pct})\n\n"
                f"**Key Project Decision Factors Driving Evaluation:**\n"
                f"• Regulatory Criticality: **{rec.factor_evaluations['regulatory_criticality'].score}/5** ({rec.factor_evaluations['regulatory_criticality'].evidence_quote})\n"
                f"• Security & Fraud Risk: **{rec.factor_evaluations['security_risk'].score}/5** ({rec.factor_evaluations['security_risk'].evidence_quote})\n"
                f"• Requirement Stability: **{rec.factor_evaluations['requirement_stability'].score}/5** ({rec.factor_evaluations['requirement_stability'].evidence_quote})\n"
                f"• Need for Continuous Delivery: **{rec.factor_evaluations['need_for_continuous_delivery'].score}/5** ({rec.factor_evaluations['need_for_continuous_delivery'].evidence_quote})\n\n"
                f"{tradeoff_text}\n\n"
                f"---\n"
                f"📄 **Updated IEEE 29148 SRS Document:**\n"
                f"The complete 23-Section Software Requirements Specification has been updated and re-compiled with the **{target_model.value}** 10-dimension workflow phases. "
                f"You can download the updated document below."
            )
            cards = [sdlc_card.model_dump(mode="json"), pdf_card.model_dump(mode="json")]
        else:
            # Informational / Challenge explanation
            sdlc_card = sdlc_agent.build_sdlc_ranking_card(rec)
            sdlc_card.actions = ["Switch to Waterfall", "Switch to V-Model", "Switch to Agile", "Switch to Agile + DevSecOps", "Adopt Recommendation"]
            
            top_rank = rec.rankings[0]
            response_text = (
                f"### 🛠️ SDLC Methodology & Factor Analysis\n\n"
                f"**Recommended Methodology:** **{rec.selected_model.value}** ({top_rank.score_percentage}% Compatibility)\n\n"
                f"**Evaluation based on your {len(existing_reqs)} active requirements:**\n"
                f"{rec.explanation}\n\n"
                f"💡 **Interactive Model Challenge:**\n"
                f"You can challenge this recommendation or switch to an alternative model by clicking any of the options below (or replying e.g. *'change to waterfall'* or *'use agile'*):"
            )
            cards = [sdlc_card.model_dump(mode="json")]

        # Log execution
        exec_log = AgentExecutionModel(
            id=str(uuid.uuid4()),
            chat_id=chat.id,
            agent_name="sdlc_agent",
            phase="sdlc_challenge",
            input_payload=json.dumps({"action": "sdlc_challenge", "user_text": user_text}),
            output_payload=json.dumps({"selected_model": rec.selected_model.value}),
            duration_ms=int((time.time() - start_time) * 1000),
            status="success"
        )
        db.add(exec_log)
        record_audit_event(
            db_session=db,
            event_type=AuditEventType.SDLC_SELECTION.value,
            actor="Coordinator",
            payload={"selected_model": rec.selected_model.value, "user_text": user_text},
            chat_id=chat.id
        )
        db.commit()

        return {
            "chat_id": chat.id,
            "project_id": project.id,
            "phase": ConversationPhase.DONE.value,
            "requirements": [r.statement for r in existing_reqs],
            "action_cards": cards,
            "progress_messages": progress,
            "response_text": response_text
        }

    def run_workflow(
        self,
        db: Session,
        chat: Chat,
        user_text: str,
        uploaded_chunks: Optional[List[Dict[str, Any]]] = None,
        auto_approve: bool = True
    ) -> Dict[str, Any]:
        """
        Execute the LangGraph workflow on behalf of the user message,
        enforce Rule 7 (Coordinator writes to DB), and log agent execution audit steps.
        """
        # Enforce Rule 7: verify Coordinator has DB write rights
        assert_can_write_db("coordinator")

        # 1. Get or create Project entity
        project = db.query(Project).filter(Project.chat_id == chat.id).first()
        if not project:
            project = Project(
                id=str(uuid.uuid4()),
                chat_id=chat.id,
                title=chat.title or "Financial Requirements Project",
                domain="financial_services"
            )
            db.add(project)
            db.flush()

        # Check for requirement update / addition intent
        if self._is_requirement_edit_intent(user_text):
            req_res = self._handle_requirement_edit(db=db, chat=chat, project=project, user_text=user_text)
            if req_res:
                return req_res

        # Check for SDLC change/challenge intent
        if self._is_sdlc_intent(user_text):
            sdlc_res = self._handle_sdlc_challenge(db=db, chat=chat, project=project, user_text=user_text)
            if sdlc_res:
                return sdlc_res

        # 2. Determine initial phase based on existing chat activity
        has_prior_runs = db.query(AgentExecutionModel).filter(AgentExecutionModel.chat_id == chat.id).count() > 0
        if not has_prior_runs:
            initial_phase = ConversationPhase.INTAKE.value
        else:
            initial_phase = ConversationPhase.ANSWERS_RECEIVED.value

        initial_state: AgentState = {
            "chat_id": chat.id,
            "project_id": project.id,
            "phase": initial_phase,
            "user_input": user_text,
            "uploaded_chunks": uploaded_chunks or [],
            "requirements": [],
            "issues": [],
            "assumptions": [],
            "compliance_mappings": [],
            "risks": [],
            "sdlc_recommendations": {},
            "approval_status": {"auto_approve": auto_approve},
            "action_cards": [],
            "progress_messages": [],
            "iteration_count": 0,
            "response_text": ""
        }

        config = {
            "configurable": {
                "thread_id": chat.id
            }
        }

        # 3. Stream/Invoke graph execution and record each step
        start_time = time.time()
        final_state: Dict[str, Any] = {}

        for event in self.graph.stream(initial_state, config):
            for node_name, node_output in event.items():
                node_duration_ms = int((time.time() - start_time) * 1000)

                # Log execution in agent_executions table
                exec_log = AgentExecutionModel(
                    id=str(uuid.uuid4()),
                    chat_id=chat.id,
                    agent_name=node_name,
                    phase=node_output.get("phase", "UNKNOWN"),
                    input_payload=json.dumps({"node": node_name, "user_text": user_text[:100]}),
                    output_payload=json.dumps({
                        "phase": node_output.get("phase"),
                        "num_reqs": len(node_output.get("requirements", [])),
                        "num_issues": len(node_output.get("issues", [])),
                        "num_cards": len(node_output.get("action_cards", []))
                    }),
                    duration_ms=node_duration_ms,
                    status="success"
                )
                db.add(exec_log)
                final_state.update(node_output)

        # 4. Coordinator persists extracted requirements & assumptions
        new_reqs = final_state.get("requirements", [])
        if new_reqs:
            for r in new_reqs:
                target_req_id = r["id"]
                existing_req = db.query(RequirementModel).filter(
                    RequirementModel.id == target_req_id
                ).first()
                if existing_req and existing_req.project_id == project.id:
                    continue
                while db.query(RequirementModel).filter(RequirementModel.id == target_req_id).first():
                    target_req_id = f"{r['id'][:15]}-{uuid.uuid4().hex[:6]}"

                req_model = RequirementModel(
                    id=target_req_id,
                    project_id=project.id,
                    statement=r["statement"],
                    category=r.get("category", "Functional"),
                    priority=r.get("priority", "Medium"),
                    version=1,
                    status="draft",
                    source_statement_id=r.get("source_statement_id"),
                    business_justification=r.get("business_justification")
                )
                db.add(req_model)
                db.flush()

                ver_model = RequirementVersion(
                    id=str(uuid.uuid4()),
                    requirement_id=req_model.id,
                    version=1,
                    statement=req_model.statement,
                    category=req_model.category,
                    priority=req_model.priority,
                    status=req_model.status,
                    changed_by="Coordinator",
                    change_reason="Initial extraction via Requirement Engineer Agent"
                )
                db.add(ver_model)

        # Persist assumptions
        new_assumps = final_state.get("assumptions", [])
        if new_assumps:
            for a in new_assumps:
                target_a_id = a["id"]
                existing_a = db.query(Assumption).filter(
                    Assumption.id == target_a_id
                ).first()
                if existing_a and existing_a.project_id == project.id:
                    continue
                while db.query(Assumption).filter(Assumption.id == target_a_id).first():
                    target_a_id = f"{a['id'][:15]}-{uuid.uuid4().hex[:6]}"
                assump_model = Assumption(
                    id=target_a_id,
                    project_id=project.id,
                    statement=a["statement"],
                    rationale=a.get("rationale"),
                    category=a.get("category"),
                    status=a.get("status", "unverified")
                )
                db.add(assump_model)

        # Persist issues
        new_issues = final_state.get("issues", [])
        if new_issues:
            for iss in new_issues:
                target_iss_id = iss["id"]
                existing_iss = db.query(RequirementIssueModel).filter(
                    RequirementIssueModel.id == target_iss_id
                ).first()
                if existing_iss and existing_iss.project_id == project.id:
                    continue
                while db.query(RequirementIssueModel).filter(RequirementIssueModel.id == target_iss_id).first():
                    target_iss_id = f"{iss['id'][:15]}-{uuid.uuid4().hex[:6]}"
                iss_model = RequirementIssueModel(
                    id=target_iss_id,
                    requirement_id=iss.get("requirement_id"),
                    project_id=project.id,
                    issue_type=iss["issue_type"],
                    severity=iss.get("severity", "medium"),
                    detail=iss["detail"],
                    suggestion=iss["suggestion"],
                    rationale=iss["rationale"],
                    status=iss.get("status", "open")
                )
                db.add(iss_model)

        # Persist compliance mappings
        new_mappings = final_state.get("compliance_mappings", [])
        if new_mappings:
            for m in new_mappings:
                target_map_id = m["id"]
                existing_map = db.query(ComplianceMappingModel).filter(
                    ComplianceMappingModel.id == target_map_id
                ).first()
                if existing_map and existing_map.project_id == project.id:
                    continue
                while db.query(ComplianceMappingModel).filter(ComplianceMappingModel.id == target_map_id).first():
                    target_map_id = f"{m['id'][:15]}-{uuid.uuid4().hex[:6]}"
                map_model = ComplianceMappingModel(
                    id=target_map_id,
                    requirement_id=m["requirement_id"],
                    project_id=project.id,
                    regulation_name=m.get("regulation_name", "Regulation"),
                    section_reference=m.get("section_reference", "General"),
                    citation_quote=m.get("citation_quote", ""),
                    citation_doc_id=m.get("citation_doc_id", "DOC-REG"),
                    citation_verified=m.get("citation_verified", False),
                    compliance_status=m.get("compliance_status", "compliant"),
                    control_required=m.get("control_required", ""),
                    gap_description=m.get("gap_description"),
                    escalation_flag=m.get("escalation_flag", False),
                    escalation_reason=m.get("escalation_reason"),
                    confidence_score=m.get("confidence_score", 1.0)
                )
                db.add(map_model)

        # Persist risks
        new_risks = final_state.get("risks", [])
        if new_risks:
            for r in new_risks:
                target_r_id = r["id"]
                existing_r = db.query(RiskModel).filter(
                    RiskModel.id == target_r_id
                ).first()
                if existing_r and existing_r.project_id == project.id:
                    continue
                while db.query(RiskModel).filter(RiskModel.id == target_r_id).first():
                    target_r_id = f"{r['id'][:15]}-{uuid.uuid4().hex[:6]}"
                r_model = RiskModel(
                    id=target_r_id,
                    project_id=project.id,
                    requirement_id=r.get("requirement_id"),
                    title=r.get("title", "Project Risk"),
                    category=r.get("category", "compliance"),
                    probability=r.get("probability", 1),
                    impact=r.get("impact", 1),
                    risk_score=r.get("risk_score", 1),
                    severity=r.get("severity", "low"),
                    mitigation=r.get("mitigation", "Implement operational controls"),
                    owner=r.get("owner", "Compliance & Risk Team"),
                    status=r.get("status", "identified")
                )
                db.add(r_model)

        # Persist SDLC recommendation
        sdlc_rec = final_state.get("sdlc_recommendations")
        if sdlc_rec and isinstance(sdlc_rec, dict):
            existing_rec = db.query(SDLCRecommendationModel).filter(
                SDLCRecommendationModel.project_id == project.id
            ).first()
            if not existing_rec:
                rec_model = SDLCRecommendationModel(
                    id=str(uuid.uuid4()),
                    project_id=project.id,
                    chat_id=chat.id,
                    selected_model=sdlc_rec.get("selected_model", "Agile + DevSecOps Hybrid"),
                    rankings_json=json.dumps(sdlc_rec.get("rankings", [])),
                    factors_json=json.dumps(sdlc_rec.get("factor_evaluations", {})),
                    explanation=sdlc_rec.get("explanation", ""),
                    workflow_json=json.dumps(sdlc_rec.get("workflow", [])),
                    is_approved=sdlc_rec.get("is_approved", False)
                )
                db.add(rec_model)
            else:
                existing_rec.selected_model = sdlc_rec.get("selected_model", existing_rec.selected_model)
                existing_rec.rankings_json = json.dumps(sdlc_rec.get("rankings", []))
                existing_rec.factors_json = json.dumps(sdlc_rec.get("factor_evaluations", {}))
                existing_rec.explanation = sdlc_rec.get("explanation", existing_rec.explanation)
                existing_rec.workflow_json = json.dumps(sdlc_rec.get("workflow", []))

        # Persist traceability matrix & generated documents if documentation completed
        doc_cards = [
            c for c in final_state.get("action_cards", [])
            if isinstance(c, dict) and str(c.get("card_type", "")).lower() in ("download_pdf", "actioncardtype.download_pdf", "document_export")
        ]
        if doc_cards:
            for dc in doc_cards:
                pl = dc.get("payload", {})
                sha = pl.get("sha256")
                if sha:
                    existing_doc = db.query(GeneratedDocumentModel).filter(
                        GeneratedDocumentModel.chat_id == chat.id,
                        GeneratedDocumentModel.sha256 == sha
                    ).first()
                    if not existing_doc:
                        doc_record = GeneratedDocumentModel(
                            id=str(uuid.uuid4()),
                            chat_id=chat.id,
                            project_id=project.id,
                            doc_type=pl.get("doc_type", "srs"),
                            version=pl.get("version", 1),
                            file_path=pl.get("file_path", ""),
                            sha256=sha,
                            status="signed_off" if pl.get("is_approved") else "generated"
                        )
                        db.add(doc_record)

            from backend.app.docs_gen.traceability import TraceabilityEngine
            rtm_rows = TraceabilityEngine.build_matrix(new_reqs, new_mappings, new_risks)
            TraceabilityEngine.persist_traceability(db, project.id, rtm_rows)

        # Record workflow execution in tamper-evident audit chain
        evt_type = (
            AuditEventType.INTAKE.value
            if final_state.get("phase") == ConversationPhase.QUESTIONS_SENT.value
            else AuditEventType.EXTRACTION.value
        )
        record_audit_event(
            db=db,
            event=evt_type,
            actor="coordinator",
            payload={
                "chat_id": chat.id,
                "project_id": project.id,
                "phase": final_state.get("phase"),
                "requirements_count": len(new_reqs),
                "issues_count": len(new_issues),
                "mappings_count": len(new_mappings),
                "risks_count": len(new_risks),
                "has_sdlc": bool(sdlc_rec)
            },
            chat_id=chat.id
        )

        db.commit()

        return {
            "phase": final_state.get("phase", ConversationPhase.DONE.value),
            "response_text": final_state.get("response_text", "Requirements processed through agent orchestration workflow."),
            "action_cards": final_state.get("action_cards", []),
            "progress_messages": final_state.get("progress_messages", []),
            "requirements": new_reqs,
            "issues": new_issues,
            "compliance_mappings": new_mappings,
            "risks": new_risks,
            "sdlc_recommendations": sdlc_rec
        }


coordinator_agent = CoordinatorAgent()
