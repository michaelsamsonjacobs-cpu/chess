(function () {
  const html = document.documentElement;
  html.classList.remove('no-js');

  const body = document.body;
  const themeToggle = document.getElementById('theme-toggle');
  const THEME_KEY = 'kcg-theme';
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

  const applyTheme = (theme) => {
    const isDark = theme === 'dark';
    body.classList.toggle('dark-theme', isDark);
    body.classList.toggle('light-theme', !isDark);
    if (themeToggle) {
      themeToggle.setAttribute('aria-pressed', String(isDark));
    }
  };

  const storedTheme = localStorage.getItem(THEME_KEY);
  if (storedTheme === 'dark' || storedTheme === 'light') {
    applyTheme(storedTheme);
  } else {
    applyTheme(prefersDark.matches ? 'dark' : 'light');
  }

  themeToggle?.addEventListener('click', () => {
    const wantsDark = !body.classList.contains('dark-theme');
    const theme = wantsDark ? 'dark' : 'light';
    applyTheme(theme);
    localStorage.setItem(THEME_KEY, theme);
  });

  const onPrefersChange = (event) => {
    if (!localStorage.getItem(THEME_KEY)) {
      applyTheme(event.matches ? 'dark' : 'light');
    }
  };

  if (typeof prefersDark.addEventListener === 'function') {
    prefersDark.addEventListener('change', onPrefersChange);
  } else if (typeof prefersDark.addListener === 'function') {
    prefersDark.addListener(onPrefersChange);
  }

  const navToggle = document.querySelector('.site-nav__toggle');
  const navList = document.getElementById('primary-menu');

  const closeNav = () => {
    navToggle?.setAttribute('aria-expanded', 'false');
    navList?.setAttribute('aria-expanded', 'false');
  };

  const openNav = () => {
    navToggle?.setAttribute('aria-expanded', 'true');
    navList?.setAttribute('aria-expanded', 'true');
  };

  const syncNavForViewport = () => {
    if (!navList) return;
    if (window.innerWidth <= 960) {
      const expanded = navToggle?.getAttribute('aria-expanded') === 'true';
      navList.setAttribute('aria-expanded', String(expanded));
    } else {
      navList.setAttribute('aria-expanded', 'true');
      navToggle?.setAttribute('aria-expanded', 'false');
    }
  };

  navToggle?.addEventListener('click', () => {
    if (window.innerWidth > 960) return;
    const isExpanded = navToggle.getAttribute('aria-expanded') === 'true';
    if (isExpanded) {
      closeNav();
    } else {
      openNav();
    }
  });

  navList?.addEventListener('click', (event) => {
    if (window.innerWidth > 960) return;
    const target = event.target;
    if (target instanceof HTMLAnchorElement) {
      closeNav();
    }
  });

  window.addEventListener('resize', syncNavForViewport);
  syncNavForViewport();

  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && window.innerWidth <= 960) {
      closeNav();
    }
  });

  const yearSpan = document.getElementById('year');
  if (yearSpan) {
    yearSpan.textContent = String(new Date().getFullYear());
  }

  const testimonialSlider = document.querySelector('.testimonial-slider');
  const testimonials = testimonialSlider ? Array.from(testimonialSlider.querySelectorAll('.testimonial')) : [];
  const sliderDots = testimonialSlider ? Array.from(testimonialSlider.querySelectorAll('.slider-dot')) : [];
  let activeIndex = testimonials.findIndex((item) => item.getAttribute('aria-hidden') === 'false');
  if (activeIndex < 0) activeIndex = 0;

  const updateSlider = (nextIndex) => {
    if (!testimonials.length || !sliderDots.length) return;
    const targetIndex = (nextIndex + testimonials.length) % testimonials.length;
    testimonials.forEach((item, index) => {
      const isActive = index === targetIndex;
      item.setAttribute('aria-hidden', String(!isActive));
      if (isActive) {
        item.removeAttribute('tabindex');
      } else {
        item.setAttribute('tabindex', '-1');
      }
    });
    sliderDots.forEach((dot, index) => {
      dot.setAttribute('aria-pressed', String(index === targetIndex));
    });
    activeIndex = targetIndex;
  };

  sliderDots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      updateSlider(index);
      resetAutoRotate();
    });
  });

  testimonialSlider?.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      updateSlider(activeIndex + 1);
      resetAutoRotate();
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      updateSlider(activeIndex - 1);
      resetAutoRotate();
    }
  });

  let autoRotateTimer = 0;
  const startAutoRotate = () => {
    if (!testimonials.length) return;
    stopAutoRotate();
    autoRotateTimer = window.setInterval(() => {
      updateSlider(activeIndex + 1);
    }, 8000);
  };

  const stopAutoRotate = () => {
    if (autoRotateTimer) {
      window.clearInterval(autoRotateTimer);
      autoRotateTimer = 0;
    }
  };

  const resetAutoRotate = () => {
    stopAutoRotate();
    startAutoRotate();
  };

  testimonialSlider?.addEventListener('pointerenter', stopAutoRotate);
  testimonialSlider?.addEventListener('pointerleave', startAutoRotate);

  updateSlider(activeIndex);
  startAutoRotate();
})();
