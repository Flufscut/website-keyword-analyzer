// API Configuration
const API_URL = process.env.API_URL || 'http://localhost:5001';

// Utility function for API calls
async function analyzeDomains(domains) {
    const url = `${API_URL}/analyze`;
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ domains })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Analysis failed');
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

    // Handle file upload form submission
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const fileInput = document.getElementById('csvFile');
        const file = fileInput.files[0];

        if (!file) {
            showError('Please select a file to upload');
            return;
        }

        try {
            // Show progress section
            hideAllSections();
            progressSection.classList.remove('d-none');
            updateProgress(0, 'Reading file...');

            // Read CSV file
            const domains = await readCSVFile(file);
            if (!domains.length) {
                throw new Error('No valid domains found in file');
            }

            // Start analysis
            updateProgress(20, 'Analyzing domains...');
            const data = await analyzeDomains(domains);
            
            // Show results
            updateProgress(100, 'Analysis complete!');
            updateResults(data);
            showResults();

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
            updateProgress(20, 'Analyzing domains...');

            // Start analysis
            const data = await analyzeDomains(domains);
            
            // Show results
            updateProgress(100, 'Analysis complete!');
            updateResults(data);
            showResults();

        } catch (error) {
            showError(error.message);
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

    async function readCSVFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const text = e.target.result;
                    const lines = text.split('\n');
                    const headers = lines[0].toLowerCase().split(',');
                    const domainIndex = headers.indexOf('domain');
                    
                    if (domainIndex === -1) {
                        throw new Error('CSV file must have a "domain" column');
                    }

                    const domains = lines.slice(1)
                        .map(line => line.split(',')[domainIndex].trim())
                        .filter(domain => domain.length > 0);

                    resolve(domains);
                } catch (error) {
                    reject(error);
                }
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    }

    function updateProgress(progress, message) {
        const percentage = Math.round(progress);
        progressBar.style.width = `${percentage}%`;
        progressBar.textContent = `${percentage}%`;
        statusText.textContent = message;
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
        
        // Show upload form
        hideAllSections();
        
        // Switch to first tab
        const uploadTab = document.querySelector('#upload-tab');
        const tab = new bootstrap.Tab(uploadTab);
        tab.show();
    }
}); 