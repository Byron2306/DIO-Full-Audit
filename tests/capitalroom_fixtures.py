from __future__ import annotations

from capitalroom import build_capitalroom
from capitalroom.proof_room import EXPECTED_WAVE_STATES, PRODUCT_IDS

GENERATED = "2026-08-11T20:30:00+00:00"

def phase0() -> dict:
    return {"snapshot_id":"SNAP-TEST","overall_state":"READY","blockers":[],"path":"/home/byron/DIO/state/system_snapshots/latest.json"}

def incarnation() -> dict:
    return {"state":"READY_FOR_FUSION","blockers":[],"receipt":"/home/byron/DIO/receipts/incarnation-latest.json"}

def wave_receipts() -> dict[int, dict]:
    receipts={wave:{"schema":f"dio.fusion.wave{wave}.receipt.v1","state":state,"blockers":[],"receipt":f"/home/byron/DIO/receipts/fusion-wave{wave}-latest.json"} for wave,state in EXPECTED_WAVE_STATES.items()}
    receipts[4].update(kernel_authority="Valinor",execution_identity_authority="ARDA")
    receipts[5].update(automatic_external_actions=0)
    receipts[6].update(composition_authority=False,kernel_authority="Valinor",execution_identity_authority="ARDA")
    receipts[7].update(twin_authority=False,loki_mirror_authority=False,loki_mirror_execution=False,kernel_authority="Valinor",execution_identity_authority="ARDA")
    receipts[8].update(continuous_assurance_authority=False,continuous_assurance_execution=False,automatic_external_notifications=0,kernel_authority="Valinor",execution_identity_authority="ARDA")
    return receipts

def portfolio() -> dict:
    names={
        "dio_assurance":"DIO Assurance","dio_agent_authority":"DIO Agent Authority","dio_vendorproof":"DIO VendorProof",
        "dio_accreditation":"DIO Accreditation","dio_tenderproof":"DIO TenderProof","dio_grantproof":"DIO GrantProof",
        "dio_research_integrity":"DIO Research Integrity","dio_regops":"DIO RegOps","dio_capitalroom":"DIO CapitalRoom",
    }
    products=[]
    for product_id in PRODUCT_IDS:
        products.append({
            "id":product_id,"name":names[product_id],"category":"test_category",
            "status":"internal_architecture_seeded" if product_id=="dio_capitalroom" else "architecture_seeded_external_validation_required",
            "runtime_mode":"internal_only" if product_id=="dio_capitalroom" else "review_workflow",
            "customer_facing":product_id!="dio_capitalroom","campaign_enabled":product_id!="dio_capitalroom",
            "risk_boundary":"Human authority remains required.","activation_gates":["independent pilot"],
        })
    return {"schema":"dio.product_portfolio.v1","truth_boundary":"Registered does not mean product proven.","products":products}

def vertical_registry() -> dict:
    executors=[]
    for index in range(8):
        executors.append({"executor_id":f"executor_{index}","capabilities":[
            {"capability":f"bound_{index}","binding_state":"bound","entrypoint_kind":"core_callable","entrypoint_ref":f"module_{index}.py:run","external_side_effect":index<3,"consequence_class":"external" if index<3 else "reversible_internal"},
            {"capability":f"locked_{index}","binding_state":"locked","entrypoint_kind":"none","entrypoint_ref":None,"external_side_effect":True,"consequence_class":"external","lock_reason":f"Capability {index} is not proven."},
        ]})
    return {"schema":"dio.vertical_executors.registry.v1","laws":{"automatic_external_actions":False},"executors":executors}

def make_room() -> dict:
    return build_capitalroom(
        phase0_snapshot=phase0(),incarnation_receipt=incarnation(),wave_receipts=wave_receipts(),
        product_portfolio=portfolio(),vertical_registry=vertical_registry(),generated_at=GENERATED,
    )
