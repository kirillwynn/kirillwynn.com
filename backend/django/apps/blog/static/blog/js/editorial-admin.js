(() => {
    "use strict";

    const enhanceValidation = () => {
        const writingSurface = document.querySelector(
            '[data-editorial-surface="writing"]',
        );
        if (!writingSurface) {
            return;
        }

        const errorContainers = writingSurface.querySelectorAll(
            "[data-field-errors]",
        );
        errorContainers.forEach((container) => {
            if (!container.textContent.trim()) {
                return;
            }

            container.setAttribute("role", "alert");
            container.setAttribute("aria-live", "polite");
        });

        const firstInvalidControl = writingSurface.querySelector(
            '[aria-invalid="true"]:is(input:not([type="hidden"]), textarea, select, button, [contenteditable="true"])',
        );
        if (!(firstInvalidControl instanceof HTMLElement)) {
            return;
        }

        requestAnimationFrame(() => {
            const activeElement = document.activeElement;
            if (activeElement !== document.body && activeElement !== null) {
                return;
            }

            firstInvalidControl.focus({ preventScroll: true });
            firstInvalidControl.scrollIntoView({
                behavior: "auto",
                block: "center",
                inline: "nearest",
            });
        });
    };

    if (document.readyState === "complete") {
        enhanceValidation();
    } else {
        window.addEventListener("load", enhanceValidation, { once: true });
    }
})();
