(function(){
    document.addEventListener('DOMContentLoaded', function(){
        var editorElement = document.getElementById('editor');
        var hiddenInput = document.getElementById('body_md') || document.querySelector('input[name="body_md"]');

        if (!editorElement || !hiddenInput || typeof window.toastui === 'undefined' || typeof window.toastui.Editor !== 'function') {
            return;
        }

        var editor = new window.toastui.Editor({
            el: editorElement,
            height: '480px',
            initialEditType: 'markdown',
            previewStyle: 'vertical',
            initialValue: hiddenInput.value || '',
            usageStatistics: false
        });

        if (editor && typeof editor.focus === 'function') {
            editor.focus();
        }

        var form = hiddenInput.form;
        if (form) {
            form.addEventListener('submit', function(){
                if (editor && typeof editor.getMarkdown === 'function') {
                    hiddenInput.value = editor.getMarkdown();
                }
            });
        }
    });
})();
