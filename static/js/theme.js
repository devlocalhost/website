document.addEventListener('DOMContentLoaded', function() {
    var savedTheme = localStorage.getItem('theme');
    var link = document.getElementById('themeStyle');

    if (savedTheme === 'light') link.href = '/static/css/light.css';
    else link.href = '/static/css/dark.css';

    console.log(`theme: ${savedTheme}`);
    console.log(`link: ${link}`);

    var toggle = document.getElementById('themeToggle');
    if (toggle) {
        toggle.onclick = function(e) {
            e.preventDefault();
            if (link.href.includes('dark.css')) {
                link.href = '/static/css/light.css';
                localStorage.setItem('theme', 'light');
            } else {
                link.href = '/static/css/dark.css';
                localStorage.setItem('theme', 'dark');
            }
        };
    }
});
