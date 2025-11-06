# Back Button Snippet for Reports

## CSS Styles

Add this CSS to your report's `<style>` section:

```css
.back-btn {
    position: absolute;
    left: 24px;
    top: 50%;
    transform: translateY(-50%);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--ink);
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
    transition: all 0.2s ease;
    z-index: 10;
}

.back-btn:hover {
    background: var(--brand);
    color: white;
    border-color: var(--brand);
    transform: translateY(-50%) translateX(-2px);
    box-shadow: 0 2px 8px rgba(75, 123, 236, 0.3);
}

.back-btn svg {
    width: 16px;
    height: 16px;
}
```

## HTML Snippet

Add this HTML right after opening your `<div class="hdr">` tag:

```html
<a href="index.html" class="back-btn">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 12H5M12 19l-7-7 7-7"/>
    </svg>
    Back to Dashboard
</a>
```

## Important Notes

1. Make sure your header has `position: relative` for absolute positioning to work
2. Adjust `left: 24px` if your header padding differs
3. The button links to `index.html` - adjust the path if your reports are in subdirectories

