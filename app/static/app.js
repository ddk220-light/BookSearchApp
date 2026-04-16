const screens = ['capture-screen', 'loading-screen', 'results-screen', 'confirm-screen', 'error-screen'];

function showScreen(id) {
    screens.forEach(s => {
        document.getElementById(s).classList.remove('active');
    });
    document.getElementById(id).classList.add('active');
}

function resetApp() {
    showScreen('capture-screen');
}

function setLoadingText(text) {
    document.getElementById('loading-text').textContent = text;
}

function showError(text) {
    document.getElementById('error-text').textContent = text;
    showScreen('error-screen');
}

// File input handlers
document.getElementById('camera-input').addEventListener('change', handleFile);
document.getElementById('upload-input').addEventListener('change', handleFile);

let scanResult = null;

async function handleFile(e) {
    const file = e.target.files[0];
    if (!file) return;

    showScreen('loading-screen');
    setLoadingText('Reading cover...');

    const formData = new FormData();
    formData.append('image', file);

    try {
        setLoadingText('Analyzing book...');
        const response = await fetch('/api/scan', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json();
            showError(err.detail || 'Something went wrong. Try again.');
            return;
        }

        scanResult = await response.json();
        displayResults(scanResult);
    } catch (err) {
        showError('Network error. Check your connection and try again.');
    }

    // Reset file inputs so the same file can be selected again
    e.target.value = '';
}

function displayResults(data) {
    // Title & author
    document.getElementById('book-title').textContent = data.title;
    document.getElementById('book-author').textContent = data.author;

    // Closed book: cover image + Goodreads rating side
    setupClosedBook(data);

    // Rating badges
    const badges = document.getElementById('rating-badges');
    badges.innerHTML = '';

    if (data.ratings.goodreads) {
        badges.innerHTML += '<span class="badge badge-goodreads">Goodreads ' + data.ratings.goodreads.rating + '</span>';
    }
    if (data.ratings.google_books) {
        badges.innerHTML += '<span class="badge badge-google">Google ' + data.ratings.google_books.rating + '</span>';
    }
    if (data.ratings.llm) {
        const tier = data.ratings.llm.quality_tier.replace(/_/g, ' ');
        badges.innerHTML += '<span class="badge badge-llm">' + tier + '</span>';
    }

    // Recommendation card
    const card = document.getElementById('recommendation-card');
    const verdict = data.recommendation.verdict;
    let cardClass = 'no-data';
    let icon = '';

    if (verdict === 'Recommended') { cardClass = 'recommended'; icon = '&#128077;'; }
    else if (verdict === 'Mixed Reviews' || verdict === 'Mixed Signals') { cardClass = 'mixed'; icon = '&#129300;'; }
    else if (verdict === 'Not Recommended') { cardClass = 'not-recommended'; icon = '&#128078;'; }

    card.className = 'recommendation-card ' + cardClass;
    card.innerHTML = '<div class="verdict">' + icon + ' ' + verdict + '</div>' +
        '<div class="summary">' + data.recommendation.summary + '</div>';

    // Library section
    const libSection = document.getElementById('library-section');
    const holdBtn = document.getElementById('hold-btn');

    if (data.library && data.library.available) {
        const best = data.library.best_edition;
        let libHtml = '<h3>Burlingame Library</h3>';

        if (best) {
            const waitText = best.estimated_wait_days === 0 ? 'Available now' : '~' + best.estimated_wait_days + ' day wait';
            libHtml += '<p>' + best.format + ' &middot; ' + waitText + '</p>';
        }

        if (data.library.editions.length > 0) {
            libHtml += '<p>' + data.library.editions.length + ' physical edition(s) found</p>';
        }

        libSection.innerHTML = libHtml;
        holdBtn.style.display = 'block';
        holdBtn.onclick = function() { placeHold(best.id, data.title); };
    } else {
        libSection.innerHTML = '<h3>Burlingame Library</h3><p>Not available in catalog</p>';
        holdBtn.style.display = 'none';
    }

    showScreen('results-screen');
}

function setupClosedBook(data) {
    const goodreads = data.ratings.goodreads;
    const ratingSide = document.getElementById('goodreads-side');
    const book = document.getElementById('book-3d');
    const cover = document.getElementById('book-cover-front');
    const reviewsSection = document.getElementById('reviews-section');

    // Reset open state for repeat scans
    book.classList.remove('open');
    reviewsSection.classList.remove('visible');

    // Goodreads rating on the left of the closed book
    if (goodreads && goodreads.rating != null) {
        const stars = renderStars(goodreads.rating);
        const count = goodreads.count ? formatCount(goodreads.count) + ' ratings' : '';
        ratingSide.classList.remove('empty');
        ratingSide.innerHTML =
            '<div class="gr-label">Goodreads</div>' +
            '<div class="gr-rating">' + goodreads.rating.toFixed(2) + '</div>' +
            '<div class="gr-stars">' + stars + '</div>' +
            (count ? '<div class="gr-count">' + count + '</div>' : '');
    } else {
        ratingSide.classList.add('empty');
        ratingSide.innerHTML = '';
    }

    // Cover image on the closed book
    const coverUrl = goodreads && goodreads.cover_image;
    const hint = '<div class="cover-hint">Tap to open</div>';
    if (coverUrl) {
        cover.innerHTML = '<img src="' + coverUrl + '" alt="Book cover">' + hint;
    } else {
        cover.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:center;' +
            'width:100%;height:100%;padding:10px;text-align:center;font-size:13px;' +
            'color:#aaa;">' + escapeHtml(data.title) + '</div>' + hint;
    }

    // Pre-render reviews so they're ready when the book opens
    renderReviews(goodreads ? goodreads.reviews : []);

    // Click to open the book
    book.onclick = function () {
        if (book.classList.contains('open')) return;
        book.classList.add('open');
        // Reveal reviews after the cover finishes rotating
        setTimeout(function () {
            reviewsSection.classList.add('visible');
        }, 700);
    };
}

function renderReviews(reviews) {
    const section = document.getElementById('reviews-section');
    if (!reviews || reviews.length === 0) {
        section.innerHTML =
            '<h3>Goodreads Reviews</h3>' +
            '<p class="reviews-empty">No reviews available.</p>';
        return;
    }
    let html = '<h3>Goodreads Reviews</h3>';
    reviews.forEach(function (r) {
        html +=
            '<div class="review-card">' +
                '<div class="review-meta">' +
                    '<span class="review-author">' + escapeHtml(r.author || 'Goodreads reader') + '</span>' +
                    (r.rating ? '<span class="review-rating">' + escapeHtml(r.rating) + '</span>' : '') +
                '</div>' +
                '<div class="review-text">' + escapeHtml(r.text) + '</div>' +
            '</div>';
    });
    section.innerHTML = html;
}

function renderStars(rating) {
    const full = Math.floor(rating);
    const half = rating - full >= 0.5 ? 1 : 0;
    const empty = 5 - full - half;
    return '\u2605'.repeat(full) + (half ? '\u00BD' : '') + '\u2606'.repeat(empty);
}

function formatCount(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(n);
}

function escapeHtml(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

async function placeHold(editionId, title) {
    const holdBtn = document.getElementById('hold-btn');
    holdBtn.disabled = true;
    holdBtn.textContent = 'Placing hold...';

    try {
        const response = await fetch('/api/hold', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ edition_id: editionId, title: title }),
        });

        const result = await response.json();

        if (result.success) {
            const details = document.getElementById('confirm-details');
            details.innerHTML = '<div>' + result.details.title + '</div>' +
                '<div>' + (result.details.format || '') + ' &middot; ' + result.details.library + '</div>';
            const libLink = document.getElementById('library-link');
            libLink.href = 'https://burlingame.bibliocommons.com' + editionId;
            showScreen('confirm-screen');
        } else {
            showError(result.message);
        }
    } catch (err) {
        showError('Network error while placing hold. Try again.');
    }

    holdBtn.disabled = false;
    holdBtn.textContent = 'Place Hold';
}
