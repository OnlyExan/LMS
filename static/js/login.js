// Get the login form
const loginForm = document.getElementById("loginForm");

// Handle login form submission
loginForm.addEventListener("submit", function (event) {

    // Prevent the default form submission
    event.preventDefault();

    // Navigate to the dashboard
    window.location.href = "/dashboard/";

});
