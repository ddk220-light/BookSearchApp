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
