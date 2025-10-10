document.addEventListener("click", async (e) => {
    if (e.target.classList.contains("block-company-btn")) {
        e.preventDefault();
        const btn = e.target;
        const companyId = btn.dataset.companyId;

        if (!confirm("Biztosan tiltólistára helyezed ezt a céget?")) return;

        const response = await fetch(`/company/block_company/${companyId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });

        const result = await response.json();

        if (result.success) {
            btn.disabled = true;
            btn.style.opacity = "0.5";
            btn.title = "Cég tiltva";
        } else {
            alert(result.error || "Hiba történt a tiltás közben.");
        }
    }
});
