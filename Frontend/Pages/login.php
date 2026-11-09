<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#f4f8f7">
    <title>Welcome to MedPredict</title>

    <link rel="stylesheet" href="../CSS/login.css">
</head>
<body>

    <div class="container">
        <div class="box">
            <aside class="auth-intro">
                <a class="brand" href="login.php"><span class="brand-mark">M</span> MedPredict</a>
                <div class="auth-message">
                    <p class="eyebrow">A CLEARER VIEW OF YOUR HEALTH</p>
                    <h1>Care begins with understanding.</h1>
                    <p>Keep your health information in one place and make sense of your lab results with a clearer overview.</p>
                </div>
                <p class="auth-footnote">For information only. Not a substitute for professional medical advice.</p>
            </aside>

            <main class="auth-form-panel">
            <div id="loginSection" class="auth-section">
                <p class="form-eyebrow">WELCOME BACK</p>
                <h2>Login</h2>
                <p class="form-intro">Sign in to continue to your health overview.</p>
                <form   id="loginForm" 
                        name="registerForm"
                        action="../../Backend/loginVerify.php"
                        method="POST"
                        onsubmit="return loginVerify()">


                    <label for="email_login">Email</label>
                    <div class="mobile-input">
                        <input
                            type="email"
                            id="email_login"
                            name="email_login"
                            placeholder="Enter registered email"
                            required
                        >
                    </div>
                    <label for="loginPassword">Password</label>
                    <input
                        type="password"
                        id="loginPassword"
                        name="loginPassword"
                        placeholder="Enter your password"
                        required
                    >

                     <input type="hidden" name="loginNew" value="1">

                    <button type="submit">
                        Login
                    </button>
                </form>


                <div class="switch">
                    <span>Don't have an account?</span>

                    <a href="#" id="showRegister">
                        Create Account
                    </a>
                </div>
            </div>

            <div id="registerSection" class="auth-section">

                <p class="form-eyebrow">GET STARTED</p>
                <h2>Create Account</h2>
                <p class="form-intro">Create your account to keep your health overview together.</p>

                <form   id="registerForm"
                        name="registerForm"
                        action="../../Backend/register.php"
                        method="POST"
                        onsubmit="return registerNew()">

                    <label for="name">Full Name</label>
                    <input
                        type="text"
                        id="name"
                        name="name"
                        placeholder="Enter your full name"
                        required
                    >
                    <label for="registerMobile">Mobile Number</label>
                    <div class="mobile-input">
                        <span>+91</span>
                        <input
                            type="tel"
                            id="registerMobile"
                            name="registerMobile"
                            placeholder="Enter 10-digit mobile number"
                            maxlength="10"
                            required
                        >
                    </div>

                    <label for="Gender">Gender</label>
                    <select id="Gender" name="Gender" required>
                        <option value="" selected disabled>Select your gender</option>
                        <option value="1">Male</option>
                        <option value="0">Female</option>
                    </select>
                    <label for="dob">Date of Birth</label>

                    <input
                        type="date"
                        id="dob"
                        name="dob"
                         required
                    >

                    <label for="email">Email</label>

                    <input type="email"  id="email"  name="email" placeholder="Enter your email" required >

                    <label for="registerPassword">Password</label>

                    <input
                        type="password"
                        id="registerPassword"
                        name="registerPassword"
                        placeholder="Create password"
                        minlength="8"
                        required
                    >
                    <small> Minimum 8 characters with at least one letter and one symbol.</small>
                    <label for="confirmPassword">Confirm Password</label>
                    <input
                        type="password"
                        id="confirmPassword"
                        name="confirmPassword"
                        placeholder="Confirm password"
                        required
                    >
                    <input type="hidden" name="registerNew" value="1">
                    <button type="submit">   Create Account</button>

                </form>

                <div class="switch">
                    <span>Already have an account?</span>

                    <a href="#" id="showLogin">
                        Login
                    </a>
                </div>
                </main>

            </div>

        </div>

    </div>


    <script src="../script/login.js"></script>

    

  
    
</body>
</html>
