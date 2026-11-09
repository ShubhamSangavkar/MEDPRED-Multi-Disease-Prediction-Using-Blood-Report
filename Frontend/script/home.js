const reportInput = document.getElementById("bloodReport");
const fileName = document.getElementById("fileName");
const uploadForm = document.getElementById("uploadForm");
const uploadButton = document.getElementById("uploadButton");
const uploadStatus = document.getElementById("uploadStatus");
const uploadStatusMessage = document.getElementById("uploadStatusMessage");
const uploadDialogClose = document.getElementById("uploadDialogClose");

if (reportInput && fileName) {
    reportInput.addEventListener("change", function () {
        const file = this.files[0];

        if (!file) {
            fileName.textContent = "";
            return;
        }

        if (file.type !== "application/pdf") {
            alert("Please select a PDF file only.");
            this.value = "";
            fileName.textContent = "";
            return;
        }

        fileName.textContent = "Selected: " + file.name;
        uploadStatus?.classList.remove("is-error");
    });
}

if (uploadForm && uploadButton && uploadStatus && uploadStatusMessage && uploadDialogClose) {
    uploadStatus.addEventListener("cancel", function (event) {
        if (!uploadStatus.classList.contains("is-error")) {
            event.preventDefault();
        }
    });

    uploadDialogClose.addEventListener("click", function () {
        uploadStatus.close();
    });

    uploadForm.addEventListener("submit", async function (event) {
        if (!uploadForm.reportValidity()) {
            event.preventDefault();
            return;
        }

        event.preventDefault();
        uploadButton.disabled = true;
        uploadButton.textContent = "Uploading and extracting...";
        uploadStatus.classList.remove("is-error");
        uploadStatus.setAttribute("aria-busy", "true");
        uploadDialogClose.hidden = true;
        uploadStatusMessage.textContent = "Uploading your PDF and extracting lab parameters. This may take a moment.";
        uploadStatus.showModal();

        const minimumSpinnerTime = new Promise(resolve => setTimeout(resolve, 5000));

        try {
            const [response] = await Promise.all([
                fetch(uploadForm.action, {
                    method: "POST",
                    body: new FormData(uploadForm),
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                    redirect: "follow"
                }),
                minimumSpinnerTime
            ]);
            const destination = new URL(response.url, window.location.href);

            if (!response.ok || !response.redirected || destination.origin !== window.location.origin ||
                destination.pathname.toLowerCase().endsWith("/backend/upload.php")) {
                throw new Error("Upload did not complete successfully.");
            }

            window.location.assign(destination.href);
        } catch (error) {
            await minimumSpinnerTime;
            uploadStatus.classList.add("is-error");
            uploadStatus.setAttribute("aria-busy", "false");
            uploadStatusMessage.textContent = "The upload could not be completed. Please check your connection and try again.";
            uploadDialogClose.hidden = false;
            uploadButton.disabled = false;
            uploadButton.textContent = "Continue with report";
        }
    });
}