const nextButton = document.getElementById("next-btn");
const predictionDialog = document.getElementById("predictionDialog");

if (nextButton && predictionDialog) {
    let isNavigating = false;

    predictionDialog.addEventListener("cancel", function (event) {
        event.preventDefault();
    });

    nextButton.addEventListener("click", function (event) {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || isNavigating) {
            return;
        }

        event.preventDefault();
        isNavigating = true;
        nextButton.setAttribute("aria-disabled", "true");
        predictionDialog.showModal();

        window.setTimeout(function () {
            window.location.assign(nextButton.href);
        }, 5000);
    });
}