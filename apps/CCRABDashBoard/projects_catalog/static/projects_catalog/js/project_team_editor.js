// Formsets retain stable row indices; checked rows are deleted on Save changes.
for (const section of document.querySelectorAll('[data-team-formset]')) {
    const prefix = section.dataset.teamFormset;
    const total = section.querySelector(`[name="${prefix}-TOTAL_FORMS"]`);
    const rows = section.querySelector('[data-team-rows]');
    const template = section.querySelector('[data-team-empty-row]');
    section.querySelector('[data-team-add]').addEventListener('click', () => {
        const index = Number(total.value);
        const fragment = template.content.cloneNode(true);
        for (const element of fragment.querySelectorAll('*')) {
            for (const attribute of ['id', 'name', 'for']) {
                if (element.hasAttribute(attribute)) {
                    element.setAttribute(attribute, element.getAttribute(attribute).replaceAll('__prefix__', index));
                }
            }
        }
        rows.append(fragment);
        total.value = index + 1;
        rows.lastElementChild.querySelector('input:not([type="hidden"])')?.focus();
    });
}
