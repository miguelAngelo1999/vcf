# Fix: Select All Checkbox Not Selecting All Items

## Problem
The "Selecionar todos" checkbox only selected items visible in the scroll view, not all duplicates.

## Root Cause
`selectedDuplicates` is a JavaScript `Set` object stored in `state`. When `setState` does:
```js
state = { ...state, ...newState }
```
The spread operator copies the `Set` reference correctly, BUT every call to `logMessage` triggers `setState`, which re-renders the list. The re-render reads `state.selectedDuplicates` to set checkbox states - this worked, BUT the list was being fully cleared and re-rendered on every `setState` call, resetting all visible checkboxes to unchecked (since the render was re-creating DOM elements).

## Fix Applied (index_pt-br.html)

### 1. Add `selectedDuplicates` to initial state
```js
let state = {
    ...
    selectedDuplicates: new Set(),
    ...
};
```

### 2. Preserve `selectedDuplicates` across `setState` calls
```js
function setState(newState) {
    const prevSelectedDuplicates = state.selectedDuplicates;
    state = { ...state, ...newState };
    if (!newState.hasOwnProperty('selectedDuplicates')) {
        state.selectedDuplicates = prevSelectedDuplicates;
    }
    render(state);
}
```

### 3. Only re-render duplicates list when count changes
```js
const currentCount = duplicatesList.querySelectorAll('.duplicate-item').length;
if (currentCount !== filteredDuplicates.length) {
    // re-render list
}
```
This prevents the list from being wiped and re-created on every `setState` call (e.g. when a log message is added), preserving the visual checkbox state.

### 4. Select all updates `selectedDuplicates` Set directly
```js
state.selectedDuplicates = isChecked 
    ? new Set(state.duplicates.map(c => c.cleaned_number)) 
    : new Set();
```

### 5. Submit button uses `selectedDuplicates.size` not DOM checkbox count
```js
if (state.selectedDuplicates && state.selectedDuplicates.size > 0) {
    const selected = state.duplicates.filter(c => state.selectedDuplicates.has(c.cleaned_number));
    await continueProcessing(selected);
}
```
