/**
 * Postergeist Editor - Column-based drag & drop, cell resize, column resize, split
 */
(function () {
    "use strict";

    let savingInProgress = false;

    // --- API helpers ---
    async function apiSave(data) {
        savingInProgress = true;
        try {
            const resp = await fetch("/api/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
            });
            return resp.json();
        } finally {
            setTimeout(() => { savingInProgress = false; }, 1000);
        }
    }

    function reload() {
        window.location.reload();
    }

    // --- Drag & Drop between columns ---
    function initDragDrop() {
        document.querySelectorAll(".poster-column").forEach((col) => {
            new Sortable(col, {
                group: "cells",
                animation: 200,
                ghostClass: "sortable-ghost",
                chosenClass: "sortable-chosen",
                handle: ".cell-header",
                draggable: ".cell",
                onEnd: function () {
                    saveOrder();
                },
            });
        });
    }

    function saveOrder() {
        const columnsOrder = [];
        document.querySelectorAll(".poster-column").forEach((col) => {
            const cellIds = [];
            col.querySelectorAll(":scope > .cell").forEach((cell) => {
                cellIds.push(cell.dataset.id);
            });
            columnsOrder.push(cellIds);
        });
        apiSave({ action: "reorder", columns_order: columnsOrder }).then(reload);
    }

    // --- Cell resize (height) via drag handle ---
    function initCellResize() {
        document.querySelectorAll(".cell").forEach((cell) => {
            const handle = document.createElement("div");
            handle.className = "resize-handle";
            cell.appendChild(handle);

            let startY = 0;
            let startHeight = 0;
            let startFlex = 0;

            handle.addEventListener("mousedown", (e) => {
                e.preventDefault();
                e.stopPropagation();
                startY = e.clientY;
                startHeight = cell.offsetHeight;
                startFlex = parseFloat(cell.dataset.height) || 1;

                const onMove = (ev) => {
                    const dy = ev.clientY - startY;
                    const ratio = (startHeight + dy) / startHeight;
                    const newFlex = Math.max(0.2, startFlex * ratio);
                    cell.style.flex = newFlex;
                    cell.dataset.height = newFlex.toFixed(2);
                };

                const onUp = () => {
                    document.removeEventListener("mousemove", onMove);
                    document.removeEventListener("mouseup", onUp);
                    const newHeight = parseFloat(cell.dataset.height) || 1;
                    apiSave({
                        action: "resize",
                        cell_id: cell.dataset.id,
                        height: newHeight,
                    }).then(() => {
                        if (typeof scaleAllCells === "function") scaleAllCells();
                    });
                };

                document.addEventListener("mousemove", onMove);
                document.addEventListener("mouseup", onUp);
            });
        });
    }

    // --- Column resize via drag dividers ---
    function initColumnResize() {
        const columns = Array.from(document.querySelectorAll(".poster-column"));
        const body = document.getElementById("poster-body");
        if (columns.length < 2 || !body) return;

        // Insert dividers as absolutely positioned overlays (not flex children)
        body.style.position = "relative";
        for (let i = 0; i < columns.length - 1; i++) {
            const divider = document.createElement("div");
            divider.className = "column-divider";
            divider.dataset.colIdx = i;
            body.appendChild(divider);

            // Position divider at the right edge of the left column
            function positionDivider() {
                const leftRect = columns[i].getBoundingClientRect();
                const bodyRect = body.getBoundingClientRect();
                // getBoundingClientRect returns screen-space coords (affected by viewport scale)
                // but divider.style.left is in poster-body's local coordinate space
                const viewport = document.querySelector(".poster-viewport");
                const transform = getComputedStyle(viewport).transform;
                let scale = 1;
                if (transform && transform !== "none") {
                    const match = transform.match(/matrix\(([^,]+)/);
                    if (match) scale = parseFloat(match[1]);
                }
                divider.style.left = ((leftRect.right - bodyRect.left) / scale) + "px";
            }
            positionDivider();
            window.addEventListener("resize", positionDivider);

            const leftCol = columns[i];
            const rightCol = columns[i + 1];

            divider.addEventListener("mousedown", (e) => {
                e.preventDefault();
                e.stopPropagation();
                const startX = e.clientX;
                const startLeftFlex = parseFloat(leftCol.style.flex) || 1;
                const startRightFlex = parseFloat(rightCol.style.flex) || 1;
                const startLeftWidth = leftCol.offsetWidth;
                const totalWidth = startLeftWidth + rightCol.offsetWidth;
                divider.classList.add("active");
                document.body.style.cursor = "col-resize";

                // Get the viewport scale to convert screen px to poster px
                const viewport = document.querySelector(".poster-viewport");
                const transform = getComputedStyle(viewport).transform;
                let scale = 1;
                if (transform && transform !== "none") {
                    const match = transform.match(/matrix\(([^,]+)/);
                    if (match) scale = parseFloat(match[1]);
                }

                const onMove = (ev) => {
                    const dx = ev.clientX - startX;
                    const posterDx = dx / scale;

                    const leftShare = (startLeftWidth + posterDx) / totalWidth;
                    const rightShare = 1 - leftShare;

                    if (leftShare > 0.05 && rightShare > 0.05) {
                        const totalFlex = startLeftFlex + startRightFlex;
                        leftCol.style.flex = (leftShare * totalFlex).toFixed(3);
                        rightCol.style.flex = (rightShare * totalFlex).toFixed(3);
                        positionDivider();
                    }
                };

                const onUp = () => {
                    document.removeEventListener("mousemove", onMove);
                    document.removeEventListener("mouseup", onUp);
                    divider.classList.remove("active");
                    document.body.style.cursor = "";

                    // Read all column flex values and save
                    const allCols = document.querySelectorAll(".poster-column");
                    const newWidths = Array.from(allCols).map(
                        (c) => parseFloat(parseFloat(c.style.flex).toFixed(2))
                    );
                    apiSave({ action: "columns", columns: newWidths }).then(() => {
                        if (typeof scaleAllCells === "function") scaleAllCells();
                    });
                };

                document.addEventListener("mousemove", onMove);
                document.addEventListener("mouseup", onUp);
            });
        }
    }

    // --- Cell action buttons ---
    function initCellActions() {
        document.querySelectorAll(".cell").forEach((cell) => {
            if (cell.querySelector(".cell-actions")) return;

            const actions = document.createElement("div");
            actions.className = "cell-actions";

            // Split button
            if (!cell.classList.contains("split-cell")) {
                const splitBtn = document.createElement("button");
                splitBtn.className = "cell-action-btn";
                splitBtn.title = "Split cell into two";
                splitBtn.textContent = "\u2502";
                splitBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    apiSave({ action: "split", cell_id: cell.dataset.id }).then(reload);
                });
                actions.appendChild(splitBtn);
            } else {
                const mergeBtn = document.createElement("button");
                mergeBtn.className = "cell-action-btn";
                mergeBtn.title = "Merge back into one";
                mergeBtn.textContent = "\u2194";
                mergeBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    apiSave({ action: "merge", cell_id: cell.dataset.id }).then(reload);
                });
                actions.appendChild(mergeBtn);
            }

            cell.appendChild(actions);
        });
    }

    // --- Toolbar ---
    function initToolbar() {
        const body = document.getElementById("poster-body");
        if (!body) return;

        const editor = document.createElement("div");
        editor.className = "column-width-editor";

        // Preview toggle
        const viewBtn = document.createElement("button");
        viewBtn.className = "save-btn";
        viewBtn.textContent = "Preview";
        viewBtn.style.background = "#666";
        viewBtn.addEventListener("click", () => {
            const vp = document.querySelector(".poster-viewport");
            vp.classList.toggle("edit-mode");
            const isEdit = vp.classList.contains("edit-mode");
            viewBtn.textContent = isEdit ? "Preview" : "Edit";
            // Re-scale cells and refit viewport after mode toggle
            setTimeout(() => {
                if (typeof scaleAllCells === "function") scaleAllCells();
                if (typeof fitToViewport === "function") fitToViewport();
            }, 100);
        });
        editor.appendChild(viewBtn);

        // Export PDF button
        const printBtn = document.createElement("button");
        printBtn.className = "save-btn";
        printBtn.textContent = "Export PDF";
        printBtn.style.background = "#2d7d46";
        printBtn.addEventListener("click", async () => {
            printBtn.textContent = "Exporting...";
            printBtn.disabled = true;
            try {
                const resp = await fetch("/api/export-pdf", { method: "POST" });
                if (!resp.ok) throw new Error("Export failed");
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "poster.pdf";
                a.click();
                URL.revokeObjectURL(url);
            } catch (e) {
                alert("PDF export failed: " + e.message);
            } finally {
                printBtn.textContent = "Export PDF";
                printBtn.disabled = false;
            }
        });
        editor.appendChild(printBtn);

        // Info
        const info = document.createElement("span");
        info.style.opacity = "0.6";
        info.style.fontSize = "12px";
        info.textContent = "Drag column edges to resize \u2022 Drag cell bottoms to resize height \u2022 Drag headers to reorder";
        editor.appendChild(info);

        document.body.appendChild(editor);
    }

    // --- SSE live reload ---
    function initLiveReload() {
        const es = new EventSource("/events");
        let debounce = null;
        es.onmessage = function () {
            if (savingInProgress) return;
            clearTimeout(debounce);
            debounce = setTimeout(reload, 500);
        };
    }

    // --- Init ---
    window.addEventListener("load", () => {
        initDragDrop();
        initCellResize();
        initColumnResize();
        initCellActions();
        initToolbar();
        initLiveReload();
    });
})();
