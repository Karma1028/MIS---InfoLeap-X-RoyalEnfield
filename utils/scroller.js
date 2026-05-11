window.RE_Showroom = window.RE_Showroom || {
    scrollToStage: function(stageId) {
        const element = document.getElementById(stageId);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            this.highlightIndicator(stageId);
        }
    },

    highlightIndicator: function(stageId) {
        const indicators = document.querySelectorAll('.step-indicator');
        indicators.forEach(indicator => {
            if (indicator.getAttribute('data-stage') === stageId) {
                indicator.classList.add('active');
            } else {
                indicator.classList.remove('active');
            }
        });
    },

    introduceBike: function() {
        // 1. Scroll to Hero (stage-01)
        this.scrollToStage('stage-01');
        
        // 2. Wait 2.5 seconds (slightly more breathing room)
        // Ensure we don't have multiple timeouts if triggered rapidly
        if (this._introTimeout) clearTimeout(this._introTimeout);
        
        this._introTimeout = setTimeout(() => {
            // 3. Scroll to Metrics (stage-02)
            this.scrollToStage('stage-02');
        }, 2500);
    },

    init: function() {
        if (this._initialized) return;
        
        window.addEventListener('message', (event) => {
            const data = event.data;
            if (!data) return;

            if (data.type === 'SCROLL_TO_STAGE') {
                this.scrollToStage(data.stageId);
            } else if (data.type === 'INTRODUCE_BIKE') {
                this.introduceBike();
            }
        });
        
        this._initialized = true;
        console.log("RE_Showroom: Scroller engine initialized.");
    }
};

// Auto-init
window.RE_Showroom.init();
