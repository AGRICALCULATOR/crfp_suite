/**
 * CR Farm Products — Corporate Website JS
 *
 * Features:
 *  - Scroll-reveal animations (IntersectionObserver)
 *  - Product catalog category filter
 *  - Gallery lightbox (keyboard + click navigation)
 */
(function () {
    'use strict';

    /* ══════════════════════════════════════════════════════════════
       1. SCROLL REVEAL — IntersectionObserver
       ══════════════════════════════════════════════════════════════ */
    function initScrollReveal() {
        if (!('IntersectionObserver' in window)) {
            // Fallback: show everything immediately
            document.querySelectorAll('.crfarm-reveal').forEach(function (el) {
                el.classList.add('crfarm-visible');
            });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('crfarm-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        document.querySelectorAll('.crfarm-reveal').forEach(function (el) {
            observer.observe(el);
        });
    }

    /* ══════════════════════════════════════════════════════════════
       2. PRODUCT CATALOG FILTER
       ══════════════════════════════════════════════════════════════ */
    function initCatalogFilter() {
        var filterBtns = document.querySelectorAll('.crfarm-filter-btn');
        var productCards = document.querySelectorAll('.crfarm-catalog-item');

        if (!filterBtns.length || !productCards.length) return;

        filterBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var category = btn.getAttribute('data-category');

                // Toggle active state
                filterBtns.forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');

                // Filter cards
                productCards.forEach(function (card) {
                    if (category === 'all' || card.getAttribute('data-category') === category) {
                        card.style.display = '';
                        // Re-trigger reveal animation
                        card.classList.remove('crfarm-visible');
                        setTimeout(function () { card.classList.add('crfarm-visible'); }, 50);
                    } else {
                        card.style.display = 'none';
                    }
                });
            });
        });
    }

    /* ══════════════════════════════════════════════════════════════
       3. GALLERY LIGHTBOX
       ══════════════════════════════════════════════════════════════ */
    function initGallery() {
        var galleryItems = document.querySelectorAll('.crfarm-gallery-item');
        var lightbox = document.getElementById('crfarm-lightbox');
        var lightboxImg = document.getElementById('crfarm-lightbox-img');
        var closeBtn = document.getElementById('crfarm-lightbox-close');
        var prevBtn = document.getElementById('crfarm-lightbox-prev');
        var nextBtn = document.getElementById('crfarm-lightbox-next');

        if (!galleryItems.length || !lightbox || !lightboxImg) return;

        var currentIndex = 0;
        var images = [];

        // Build images array from gallery items
        galleryItems.forEach(function (item) {
            var img = item.querySelector('img');
            images.push({
                src: img ? img.src : '',
                alt: img ? (img.alt || 'CR Farm Products') : 'CR Farm Products',
            });
        });

        function openLightbox(index) {
            currentIndex = index;
            lightboxImg.src = images[index].src;
            lightboxImg.alt = images[index].alt;
            lightbox.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function closeLightbox() {
            lightbox.classList.remove('active');
            document.body.style.overflow = '';
        }

        function showPrev() {
            currentIndex = (currentIndex - 1 + images.length) % images.length;
            lightboxImg.src = images[currentIndex].src;
            lightboxImg.alt = images[currentIndex].alt;
        }

        function showNext() {
            currentIndex = (currentIndex + 1) % images.length;
            lightboxImg.src = images[currentIndex].src;
            lightboxImg.alt = images[currentIndex].alt;
        }

        // Click to open
        galleryItems.forEach(function (item, idx) {
            item.addEventListener('click', function () { openLightbox(idx); });
        });

        // Controls
        if (closeBtn) closeBtn.addEventListener('click', closeLightbox);
        if (prevBtn) prevBtn.addEventListener('click', showPrev);
        if (nextBtn) nextBtn.addEventListener('click', showNext);

        // Click backdrop to close
        lightbox.addEventListener('click', function (e) {
            if (e.target === lightbox) closeLightbox();
        });

        // Keyboard navigation
        document.addEventListener('keydown', function (e) {
            if (!lightbox.classList.contains('active')) return;
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') showPrev();
            if (e.key === 'ArrowRight') showNext();
        });
    }

    /* ══════════════════════════════════════════════════════════════
       4. INIT ON DOM READY
       ══════════════════════════════════════════════════════════════ */
    function init() {
        initScrollReveal();
        initCatalogFilter();
        initGallery();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
