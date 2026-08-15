"use strict";

const form = document.querySelector("#journey");
const result = document.querySelector("#result");
const contractFile = document.querySelector("#contract_file");
const contractText = document.querySelector("#contract_text");

contractFile.addEventListener("change", async () => {
  const file = contractFile.files[0];
  if (file) contractText.value = await file.text();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  result.hidden = false;
  result.textContent = "Resolving the controlled reference journey…";
  const fields = new FormData(form);
  const payload = {
    name: fields.get("name"), email: fields.get("email"), organisation: fields.get("organisation"),
    review_title: fields.get("review_title"), message: fields.get("message"),
    contract_text: fields.get("contract_text"), evidence_notes: fields.get("evidence_notes"),
    website_honeypot: fields.get("website_honeypot"),
    page_viewed: true, information_acknowledged: document.querySelector("#ack").checked,
    controlled_test_payment_consented: document.querySelector("#ack").checked,
  };
  try {
    const response = await fetch("/api/reference-journey", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.reason || body.error || "Journey refused");
    result.textContent = [
      "RESOLVED CONTROLLED TEST", `Journey: ${body.journey_id}`,
      `Payment truth: ${body.commercial_truth.phase10_truth_state}`,
      `Proof integrity: ${body.steps.proof_integrity}`,
      `Readable proof pack: ${body.proof_output_dir}`,
      `External delivery: ${body.gates.external_delivery}`,
      "Revenue / validation claimed: NO",
    ].join("\n");
  } catch (error) {
    result.textContent = `REFUSED: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});
