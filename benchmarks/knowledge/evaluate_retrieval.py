"""Run the model-free Knowledge golden retrieval evaluation."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.knowledge import KnowledgeStore
from ai2apps.storage import PlatformDatabase


def evaluate(fixture_path: Path, *, limit: int = 5) -> dict[str, float | int]:
    fixture = json.loads(fixture_path.read_text())
    principal = RequestPrincipal(
        actor_user_id="eval-user",
        installation_id="eval-installation",
        organization_id="eval-organization",
        billing_account_id="eval-billing",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )
    with tempfile.TemporaryDirectory(prefix="ai2apps-knowledge-eval-") as root:
        database = PlatformDatabase(Path(root) / "platform.sqlite3")
        database.initialize()
        store = KnowledgeStore(database, blob_root=Path(root) / "knowledge")
        item_keys = {}
        for document in fixture["documents"]:
            owner = str(document.get("owner", principal.actor_user_id))
            document_principal = principal if owner == principal.actor_user_id else RequestPrincipal(
                actor_user_id=owner,
                installation_id=principal.installation_id,
                organization_id=principal.organization_id,
                billing_account_id=principal.billing_account_id,
                role=MemberRole.MEMBER,
                membership_epoch=1,
            )
            item = store.create_text_item(
                document_principal,
                title=document["title"],
                text=document["text"],
            )
            item_keys[item.id] = document["key"]

        forbidden = {
            document["key"]
            for document in fixture["documents"]
            if document.get("owner", principal.actor_user_id)
            != principal.actor_user_id
        }

        recall = []
        reciprocal_ranks = []
        citation_precision = []
        no_answer = []
        answer_citation_precision = []
        answer_citation_coverage = []
        answer_claim_support = []
        citation_authorization = []
        for case in fixture["queries"]:
            returned = [
                item_keys[hit.item.id]
                for hit in store.search(principal, case["query"], limit=limit)
            ]
            expected = set(case["expected"])
            claims = case.get("answer", {}).get("claims", [])
            cited = {
                key
                for claim in claims
                for key in claim.get("citations", [])
            }
            returned_set = set(returned)
            citation_authorization.append(
                float(not ((returned_set | cited) & forbidden))
            )
            if not expected:
                no_answer.append(float(not returned and not claims and not cited))
                continue
            relevant = [
                index for index, key in enumerate(returned, 1) if key in expected
            ]
            recall.append(len(set(returned) & expected) / len(expected))
            reciprocal_ranks.append(1.0 / relevant[0] if relevant else 0.0)
            citation_precision.append(
                len(set(returned) & expected) / len(returned) if returned else 0.0
            )
            answer_citation_precision.append(
                len(cited & expected) / len(cited) if cited else 0.0
            )
            answer_citation_coverage.append(len(cited & expected) / len(expected))
            answer_claim_support.extend(
                float(
                    bool(claim.get("citations"))
                    and set(claim["citations"]) <= expected
                    and set(claim["citations"]) <= returned_set
                )
                for claim in claims
            )

    def average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 1.0

    return {
        "cases": len(fixture["queries"]),
        "recall_at_k": average(recall),
        "mrr": average(reciprocal_ranks),
        "citation_precision_at_k": average(citation_precision),
        "no_answer_accuracy": average(no_answer),
        "answer_citation_precision": average(answer_citation_precision),
        "answer_citation_coverage": average(answer_citation_coverage),
        "answer_claim_support": average(answer_claim_support),
        "citation_authorization_accuracy": average(citation_authorization),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).with_name("eval_cases.json"),
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    print(
        json.dumps(evaluate(args.fixture, limit=args.limit), indent=2, sort_keys=True)
    )


if __name__ == "__main__":
    main()
