document.querySelectorAll("[data-model-target]").forEach(function (button) {
    button.addEventListener("click", function () {
        var selectedModel = button.dataset.modelTarget;

        document.querySelectorAll("[data-model-target]").forEach(function (selector) {
            var isSelected = selector === button;
            selector.classList.toggle("is-active", isSelected);
            selector.setAttribute("aria-pressed", String(isSelected));
        });

        document.querySelectorAll("[data-model-panel]").forEach(function (panel) {
            panel.hidden = panel.dataset.modelPanel !== selectedModel;
        });
    });
});
