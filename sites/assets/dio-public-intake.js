(function () {
  "use strict";

  const endpoint = "https://dio-edge-gateway-live.dio-workflows.workers.dev/api/public/intake";

  function attribution(source) {
    const params = new URLSearchParams(window.location.search);
    return {
      source,
      medium: params.get("utm_medium") || "website",
      campaign_id: params.get("utm_campaign") || null,
      content: params.get("utm_content") || null,
      referrer: document.referrer || null,
      landing_page: window.location.href.split("#")[0],
    };
  }

  async function submit(envelope) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12_000);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema: "dio.public_intake.v1",
          submitted_at: new Date().toISOString(),
          website_honeypot: "",
          ...envelope,
        }),
        signal: controller.signal,
      });
      const receipt = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(receipt.error || `intake_http_${response.status}`);
      return receipt;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function showFallback(container, message, mailto) {
    container.textContent = `${message} `;
    const link = document.createElement("a");
    link.href = mailto;
    link.textContent = "Use the Outlook email route.";
    link.style.color = "inherit";
    link.style.fontWeight = "800";
    container.appendChild(link);
  }

  window.DIOPublicIntake = { attribution, endpoint, showFallback, submit };
}());
