document.addEventListener('DOMContentLoaded', function () {
    var savedTheme = localStorage.getItem('theme');
    var link = document.getElementById('themeStyle');

    if (savedTheme === 'light') {
        link.href = '/static/css/light.css';
    } else {
        savedTheme = 'dark';
        link.href = '/static/css/dark.css';
    }

    updateIcon(savedTheme);

    var toggle = document.getElementById('themeToggle');
    if (toggle) {
        toggle.onclick = function (e) {
            e.preventDefault();

            var next;
            if (link.href.includes('dark.css')) {
                next = 'light';
                link.href = '/static/css/light.css';
            } else {
                next = 'dark';
                link.href = '/static/css/dark.css';
            }

            localStorage.setItem('theme', next);
            updateIcon(next);
        };
    }
});

function updateIcon(theme) {
    var sun = document.getElementById('sun-icon');
    var moon = document.getElementById('moon-icon');

    if (!sun || !moon) return;

    if (theme === 'light') {
        sun.style.display = 'none';
        moon.style.display = 'block';
    } else {
        sun.style.display = 'block';
        moon.style.display = 'none';
    }
}

