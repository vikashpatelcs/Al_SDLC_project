"""
Coordinator Agent for Phase 9: Multi-Agent Orchestration.
The Coordinator is the central orchestrator and the single authoritative persistence writer (Rule 7).
It drives the LangGraph state machine, logs agent executions to `agent_executions`, and manages DB transactions.
"""
import json
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
)
from backend.app.graph.state import AgentState, ConversationPhase
from backend.app.graph.workflow import build_orchestration_graph
from backend.app.graph.checkpointer import SqliteCheckpointer


class CoordinatorAgent:
    def __init__(self, checkpointer: Optional[SqliteCheckpointer] = None):
        self.checkpointer = checkpointer or SqliteCheckpointer()
        self.graph = build_orchestration_graph(checkpointer=self.checkpointer)

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
                existing_req = db.query(RequirementModel).filter(
                    RequirementModel.id == r["id"],
                    RequirementModel.project_id == project.id
                ).first()
                if not existing_req:
                    req_model = RequirementModel(
                        id=r["id"],
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
                existing_a = db.query(Assumption).filter(
                    Assumption.id == a["id"]
                ).first()
                if not existing_a:
                    assump_model = Assumption(
                        id=a["id"],
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
                existing_iss = db.query(RequirementIssueModel).filter(
                    RequirementIssueModel.id == iss["id"]
                ).first()
                if not existing_iss:
                    iss_model = RequirementIssueModel(
                        id=iss["id"],
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

        db.commit()

        return {
            "phase": final_state.get("phase", ConversationPhase.DONE.value),
            "response_text": final_state.get("response_text", "Requirements processed through agent orchestration workflow."),
            "action_cards": final_state.get("action_cards", []),
            "progress_messages": final_state.get("progress_messages", []),
            "requirements": new_reqs,
            "issues": new_issues
        }


coordinator_agent = CoordinatorAgent()
