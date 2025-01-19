// API Configuration
const API_URL = process.env.API_URL || 'http://localhost:5001';

// Utility function for API calls
async function callAPI(endpoint, options = {}) {
    const url = `${API_URL}${endpoint}`;
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                ...options.headers,
                'Accept': 'application/json',
            }
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'API request failed');
        }
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const pasteForm = document.getElementById('pasteForm');
    const progressSection = document.getElementById('progressSection');
    const resultsSection = document.getElementById('resultsSection');
    const errorSection = document.getElementById('errorSection');
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('statusText');
    const errorText = document.getElementById('errorText');
    const downloadBtn = document.getElementById('downloadBtn');
    const newAnalysisBtn = document.getElementById('newAnalysisBtn');
    const tryAgainBtn = document.getElementById('tryAgainBtn');

    let currentTaskId = null;
    let progressCheckInterval = null;

    // Handle file upload form submission
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const fileInput = document.getElementById('csvFile');
        const file = fileInput.files[0];

        if (!file) {
            showError('Please select a file to upload');
            return;
        }

        // Create FormData object
        const formData = new FormData();
        formData.append('file', file);

        try {
            // Show progress section
            hideAllSections();
            progressSection.classList.remove('d-none');
            updateProgress(0, 'Starting analysis...');

            // Upload file
            const response = await callAPI('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            // Start progress checking
            currentTaskId = data.task_id;
            startProgressChecking();

        } catch (error) {
            showError(error.message);
        }
    });

    // Handle paste form submission
    pasteForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const domainList = document.getElementById('domainList').value.trim();
        if (!domainList) {
            showError('Please enter at least one domain');
            return;
        }

        // Convert text to array of domains
        const domains = domainList.split('\n')
            .map(domain => domain.trim())
            .filter(domain => domain.length > 0);

        if (domains.length === 0) {
            showError('Please enter at least one valid domain');
            return;
        }

        try {
            // Show progress section
            hideAllSections();
            progressSection.classList.remove('d-none');
            updateProgress(0, 'Starting analysis...');

            // Send domains
            const response = await callAPI('/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ domains: domains })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Analysis failed');
            }

            // Start progress checking
            currentTaskId = data.task_id;
            startProgressChecking();

        } catch (error) {
            showError(error.message);
        }
    });

    // Handle download button click
    downloadBtn.addEventListener('click', function() {
        if (currentTaskId) {
            window.location.href = `/download/${currentTaskId}`;
        }
    });

    // Handle new analysis button click
    newAnalysisBtn.addEventListener('click', function() {
        resetForm();
    });

    // Handle try again button click
    tryAgainBtn.addEventListener('click', function() {
        resetForm();
    });

    function startProgressChecking() {
        if (progressCheckInterval) {
            clearInterval(progressCheckInterval);
        }

        progressCheckInterval = setInterval(async function() {
            try {
                const response = await callAPI(`/status/${currentTaskId}`);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to get status');
                }

                updateProgress(data.progress, getStatusMessage(data.status));

                // Handle completion or failure
                if (data.status === 'completed') {
                    clearInterval(progressCheckInterval);
                    if (data.results) {
                        updateResults(data);
                    }
                    showResults();
                } else if (data.status === 'failed') {
                    clearInterval(progressCheckInterval);
                    showError(data.error || 'Analysis failed');
                }

            } catch (error) {
                clearInterval(progressCheckInterval);
                showError(error.message);
            }
        }, 1000);
    }

    function updateProgress(progress, message) {
        const percentage = Math.round(progress);
        progressBar.style.width = `${percentage}%`;
        progressBar.textContent = `${percentage}%`;
        statusText.textContent = message;
    }

    function getStatusMessage(status) {
        switch (status) {
            case 'starting':
                return 'Preparing to analyze domains...';
            case 'processing':
                return 'Analyzing domains...';
            case 'completed':
                return 'Analysis completed!';
            case 'failed':
                return 'Analysis failed';
            default:
                return 'Processing...';
        }
    }

    function showError(message) {
        hideAllSections();
        errorSection.classList.remove('d-none');
        errorText.textContent = message;
    }

    function showResults() {
        hideAllSections();
        resultsSection.classList.remove('d-none');
    }

    function updateResults(data) {
        const resultsTableBody = document.getElementById('resultsTableBody');
        const averageScore = document.getElementById('averageScore');
        const totalDomains = document.getElementById('totalDomains');
        const successRate = document.getElementById('successRate');

        // Clear existing results
        resultsTableBody.innerHTML = '';

        // Update table
        data.results.forEach(result => {
            const row = document.createElement('tr');
            
            // Add status class
            if (result.status.includes('Error')) {
                row.classList.add('table-danger');
            } else if (result.score >= 8) {
                row.classList.add('table-success');
            } else if (result.score >= 5) {
                row.classList.add('table-warning');
            }
            
            row.innerHTML = `
                <td>${result.domain}${result.redirected_to ? 
                    `<br><small class="text-muted">→ ${result.redirected_to}</small>` : ''}</td>
                <td>${result.score.toFixed(1)}</td>
                <td>${result.status}</td>
                <td>${result.pages_crawled}</td>
                <td>${result.total_mentions}</td>
            `;
            resultsTableBody.appendChild(row);
        });

        // Update summary stats
        averageScore.textContent = data.summary.average_score.toFixed(1);
        totalDomains.textContent = data.summary.total_domains;
        successRate.textContent = data.summary.success_rate.toFixed(1) + '%';
    }

    function hideAllSections() {
        progressSection.classList.add('d-none');
        resultsSection.classList.add('d-none');
        errorSection.classList.add('d-none');
    }

    function resetForm() {
        // Clear both forms
        uploadForm.reset();
        pasteForm.reset();
        
        // Reset task ID
        currentTaskId = null;
        
        // Clear interval
        if (progressCheckInterval) {
            clearInterval(progressCheckInterval);
        }
        
        // Show upload form
        hideAllSections();
        
        // Switch to first tab
        const uploadTab = document.querySelector('#upload-tab');
        const tab = new bootstrap.Tab(uploadTab);
        tab.show();
    }
}); 