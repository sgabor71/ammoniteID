/* ============================================================
   HAMBURGER MENU - Mobile Navigation Toggle
   Add this to your HTML pages
   ============================================================ */

document.addEventListener('DOMContentLoaded', function() {
    const hamburgerBtn = document.querySelector('.hamburger-btn');
    const nav = document.querySelector('nav');

    if (hamburgerBtn && nav) {
        // Toggle menu on hamburger click
        hamburgerBtn.addEventListener('click', function() {
            hamburgerBtn.classList.toggle('active');
            nav.classList.toggle('active');
        });

        // Close menu when a link is clicked
        const navLinks = nav.querySelectorAll('a');
        navLinks.forEach(link => {
            link.addEventListener('click', function() {
                hamburgerBtn.classList.remove('active');
                nav.classList.remove('active');
            });
        });

        // Close menu when clicking outside
        document.addEventListener('click', function(event) {
            const isClickInsideMenu = nav.contains(event.target);
            const isClickOnHamburger = hamburgerBtn.contains(event.target);
            
            if (!isClickInsideMenu && !isClickOnHamburger) {
                hamburgerBtn.classList.remove('active');
                nav.classList.remove('active');
            }
        });
    }
});
