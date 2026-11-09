
const loginSection = document.getElementById("loginSection");
const registerSection = document.getElementById("registerSection");

const showRegister = document.getElementById("showRegister");
const showLogin = document.getElementById("showLogin");



showRegister.addEventListener("click", function(event) {

    event.preventDefault();

    loginSection.style.display = "none";
    registerSection.style.display = "block";

});




showLogin.addEventListener("click", function(event) {

    event.preventDefault();

    registerSection.style.display = "none";
    loginSection.style.display = "block";

});


function loginVerify(){

// document.getElementById("loginForm").addEventListener("submit", function(event) {

//     event.preventDefault();

    const email_login =
        document.getElementById("email_login").value;

    const password =
        document.getElementById("loginPassword").value;




    // if (isNaN(email_login)) {

    //     alert("Enter email.");

    //     return false;
    // }


    if (password.length < 8) {

        alert("Password must contain at least 8 characters.");

        return false;
    }

    return true;

};



function registerNew(){
// document.getElementById("registerForm").addEventListener("submit", function(event) {

//     event.preventDefault();

    const mobile =
        document.getElementById("registerMobile").value;

    const password =
        document.getElementById("registerPassword").value;

    const confirmPassword =
        document.getElementById("confirmPassword").value;


    const mobilePattern = /^[6-9][0-9]{9}$/;

    // const passwordPattern =
    //     /^(?=.*[A-Za-z])(?=.*[^A-Za-z0-9]).{8,}$/;


    if (!mobilePattern.test(mobile)) {

        alert("Enter a valid 10-digit Indian mobile number.");

        return;
    }


    // if (!passwordPattern.test(password)) {

    //     alert(
    //         "Password must be at least 8 characters " +
    //         "and contain at least one letter and one symbol."
    //     );

    //     return;
    // }


    if (password !== confirmPassword) {

        alert("Passwords do not match.");

        return false;
    }

    alert("registerd");
    return true;

}

