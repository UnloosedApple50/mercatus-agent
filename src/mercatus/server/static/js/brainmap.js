/**
 * Mercatus Agent Dashboard — Brain Map (Knowledge Graph Visualization)
 * Canvas-based interactive graph with zoom, pan, search, and filters.
 */

(function () {
    'use strict';

    // === State ===
    const brainState = {
        canvas: null,
        ctx: null,
        nodes: [],
        edges: [],
        transform: { x: 0, y: 0, scale: 1 },
        isDragging: false,
        dragStart: { x: 0, y: 0 },
        hoveredNode: null,
        selectedNode: null,
        filterType: 'all',
        searchQuery: '',
        animationId: null,
    };

    // === Constants ===
    const NODE_RADIUS = 8;
    const FONT_SIZE = 11;
    const LABEL_OFFSET = 14;
    const MIN_SCALE = 0.2;
    const MAX_SCALE = 5;

    // === Initialization ===
    function initBrainMap() {
        brainState.canvas = document.getElementById('brainmap-canvas');
        if (!brainState.canvas) return;

        brainState.ctx = brainState.canvas.getContext('2d');
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        // Event listeners
        brainState.canvas.addEventListener('mousedown', onMouseDown);
        brainState.canvas.addEventListener('mousemove', onMouseMove);
        brainState.canvas.addEventListener('mouseup', onMouseUp);
        brainState.canvas.addEventListener('wheel', onWheel);
        brainState.canvas.addEventListener('click', onClick);
        brainState.canvas.addEventListener('dblclick', onDblClick);

        // Controls
        document.getElementById('brain-zoom-in')?.addEventListener('click', () => zoom(1.2));
        document.getElementById('brain-zoom-out')?.addEventListener('click', () => zoom(0.8));
        document.getElementById('brain-reset')?.addEventListener('click', resetView);
        document.getElementById('brain-search')?.addEventListener('input', onSearch);
        document.getElementById('brain-filter')?.addEventListener('change', onFilterChange);

        // Load data
        loadBrainData();

        // Start render loop
        render();
    }

    function resizeCanvas() {
        const container = brainState.canvas?.parentElement;
        if (!container || !brainState.canvas) return;
        brainState.canvas.width = container.clientWidth;
        brainState.canvas.height = container.clientHeight;
    }

    // === Data Loading ===
    async function loadBrainData() {
        try {
            const response = await fetch('/api/v1/brain/graph');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            brainState.nodes = data.nodes.map(n => ({
                ...n,
                x: (Math.random() - 0.5) * 400,
                y: (Math.random() - 0.5) * 400,
                vx: 0,
                vy: 0,
                radius: Math.max(NODE_RADIUS, n.size || NODE_RADIUS),
            }));
            brainState.edges = data.edges || [];

            // Run force simulation to layout nodes
            runForceSimulation();
        } catch (e) {
            console.error('Failed to load brain data:', e);
            showBrainError(e.message);
        }
    }

    function runForceSimulation() {
        const nodes = brainState.nodes;
        const edges = brainState.edges;
        const iterations = 100;

        for (let i = 0; i < iterations; i++) {
            // Repulsion between all nodes
            for (let a = 0; a < nodes.length; a++) {
                for (let b = a + 1; b < nodes.length; b++) {
                    const dx = nodes[b].x - nodes[a].x;
                    const dy = nodes[b].y - nodes[a].y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const force = 500 / (dist * dist);
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;
                    nodes[a].vx -= fx;
                    nodes[a].vy -= fy;
                    nodes[b].vx += fx;
                    nodes[b].vy += fy;
                }
            }

            // Attraction along edges
            for (const edge of edges) {
                const source = nodes.find(n => n.id === edge.source);
                const target = nodes.find(n => n.id === edge.target);
                if (!source || !target) continue;

                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const force = (dist - 100) * 0.01 * (edge.weight || 1);
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;
                source.vx += fx;
                source.vy += fy;
                target.vx -= fx;
                target.vy -= fy;
            }

            // Apply velocity with damping
            for (const node of nodes) {
                node.vx *= 0.9;
                node.vy *= 0.9;
                node.x += node.vx;
                node.y += node.vy;
            }
        }
    }

    // === Rendering ===
    function render() {
        const ctx = brainState.ctx;
        const canvas = brainState.canvas;
        if (!ctx || !canvas) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.save();
        ctx.translate(brainState.transform.x + canvas.width / 2, brainState.transform.y + canvas.height / 2);
        ctx.scale(brainState.transform.scale, brainState.transform.scale);

        // Draw edges
        drawEdges(ctx);

        // Draw nodes
        drawNodes(ctx);

        // Draw labels
        drawLabels(ctx);

        ctx.restore();

        brainState.animationId = requestAnimationFrame(render);
    }

    function drawEdges(ctx) {
        const visibleNodes = getVisibleNodes();
        const visibleIds = new Set(visibleNodes.map(n => n.id));

        ctx.strokeStyle = 'rgba(99, 102, 241, 0.2)';
        ctx.lineWidth = 1;

        for (const edge of brainState.edges) {
            if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) continue;

            const source = brainState.nodes.find(n => n.id === edge.source);
            const target = brainState.nodes.find(n => n.id === edge.target);
            if (!source || !target) continue;

            ctx.beginPath();
            ctx.moveTo(source.x, source.y);
            ctx.lineTo(target.x, target.y);
            ctx.stroke();
        }
    }

    function drawNodes(ctx) {
        const visibleNodes = getVisibleNodes();

        for (const node of visibleNodes) {
            const isHovered = brainState.hoveredNode === node.id;
            const isSelected = brainState.selectedNode === node.id;
            const radius = node.radius || NODE_RADIUS;

            // Glow effect for hovered/selected
            if (isHovered || isSelected) {
                ctx.shadowColor = node.color || '#6366f1';
                ctx.shadowBlur = 15;
            }

            // Node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = node.color || '#6366f1';
            ctx.fill();

            // Border for selected
            if (isSelected) {
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 2;
                ctx.stroke();
            }

            ctx.shadowBlur = 0;
        }
    }

    function drawLabels(ctx) {
        const visibleNodes = getVisibleNodes();
        ctx.font = `${FONT_SIZE}px Inter, sans-serif`;
        ctx.fillStyle = 'rgba(232, 234, 237, 0.9)';
        ctx.textAlign = 'center';

        for (const node of visibleNodes) {
            const radius = node.radius || NODE_RADIUS;
            const label = node.label?.length > 25 ? node.label.substring(0, 25) + '...' : node.label;
            ctx.fillText(label || node.id, node.x, node.y + radius + LABEL_OFFSET);
        }
    }

    function getVisibleNodes() {
        let nodes = brainState.nodes;

        // Apply type filter
        if (brainState.filterType !== 'all') {
            nodes = nodes.filter(n => n.type === brainState.filterType);
        }

        // Apply search filter
        if (brainState.searchQuery) {
            const query = brainState.searchQuery.toLowerCase();
            nodes = nodes.filter(n =>
                (n.label && n.label.toLowerCase().includes(query)) ||
                (n.id && n.id.toLowerCase().includes(query)) ||
                (n.metadata && JSON.stringify(n.metadata).toLowerCase().includes(query))
            );
        }

        return nodes;
    }

    // === Interaction ===
    function onMouseDown(e) {
        brainState.isDragging = true;
        brainState.dragStart = { x: e.clientX, y: e.clientY };
    }

    function onMouseMove(e) {
        if (brainState.isDragging) {
            const dx = e.clientX - brainState.dragStart.x;
            const dy = e.clientY - brainState.dragStart.y;
            brainState.transform.x += dx;
            brainState.transform.y += dy;
            brainState.dragStart = { x: e.clientX, y: e.clientY };
        } else {
            // Check hover
            const pos = screenToWorld(e.offsetX, e.offsetY);
            const hovered = findNodeAt(pos.x, pos.y);
            brainState.hoveredNode = hovered?.id || null;
            brainState.canvas.style.cursor = hovered ? 'pointer' : 'grab';
        }
    }

    function onMouseUp() {
        brainState.isDragging = false;
    }

    function onWheel(e) {
        e.preventDefault();
        const factor = e.deltaY > 0 ? 0.9 : 1.1;
        zoom(factor, e.offsetX, e.offsetY);
    }

    function onClick(e) {
        const pos = screenToWorld(e.offsetX, e.offsetY);
        const node = findNodeAt(pos.x, pos.y);
        brainState.selectedNode = node?.id || null;

        if (node) {
            showNodeDetails(node);
        }
    }

    function onDblClick(e) {
        const pos = screenToWorld(e.offsetX, e.offsetY);
        const node = findNodeAt(pos.x, pos.y);
        if (node) {
            // Center on node
            brainState.transform.x = -node.x * brainState.transform.scale;
            brainState.transform.y = -node.y * brainState.transform.scale;
        }
    }

    function zoom(factor, cx, cy) {
        const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, brainState.transform.scale * factor));
        if (newScale === brainState.transform.scale) return;

        // Zoom toward center if no point specified
        cx = cx !== undefined ? cx : brainState.canvas.width / 2;
        cy = cy !== undefined ? cy : brainState.canvas.height / 2;

        const worldX = (cx - brainState.transform.x - brainState.canvas.width / 2) / brainState.transform.scale;
        const worldY = (cy - brainState.transform.y - brainState.canvas.height / 2) / brainState.transform.scale;

        brainState.transform.scale = newScale;
        brainState.transform.x = cx - worldX * newScale - brainState.canvas.width / 2;
        brainState.transform.y = cy - worldY * newScale - brainState.canvas.height / 2;
    }

    function resetView() {
        brainState.transform = { x: 0, y: 0, scale: 1 };
    }

    function onSearch(e) {
        brainState.searchQuery = e.target.value;
    }

    function onFilterChange(e) {
        brainState.filterType = e.target.value;
    }

    // === Helpers ===
    function screenToWorld(sx, sy) {
        return {
            x: (sx - brainState.transform.x - brainState.canvas.width / 2) / brainState.transform.scale,
            y: (sy - brainState.transform.y - brainState.canvas.height / 2) / brainState.transform.scale,
        };
    }

    function findNodeAt(x, y) {
        const visible = getVisibleNodes();
        for (let i = visible.length - 1; i >= 0; i--) {
            const node = visible[i];
            const dx = x - node.x;
            const dy = y - node.y;
            const radius = (node.radius || NODE_RADIUS) + 5;
            if (dx * dx + dy * dy <= radius * radius) {
                return node;
            }
        }
        return null;
    }

    async function showNodeDetails(node) {
        const container = document.getElementById('brain-node-details');
        if (!container) return;

        container.innerHTML = `<p class="text-muted">${t('common.loading', 'Loading...')}</p>`;

        try {
            const response = await fetch(`/api/v1/brain/node/${encodeURIComponent(node.id)}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const details = await response.json();
            renderNodeDetails(container, details);
        } catch (e) {
            container.innerHTML = `<p class="text-error">Error: ${e.message}</p>`;
        }
    }

    function renderNodeDetails(container, details) {
        if (details.error) {
            container.innerHTML = `<p class="text-error">${details.error}</p>`;
            return;
        }

        let html = `<h4>${details.type || 'Node'}: ${details.id}</h4>`;

        if (details.module) html += `<p><strong>Module:</strong> ${details.module}</p>`;
        if (details.confidence !== undefined) html += `<p><strong>Confidence:</strong> ${(details.confidence * 100).toFixed(0)}%</p>`;
        if (details.category) html += `<p><strong>Category:</strong> ${details.category}</p>`;
        if (details.key) html += `<p><strong>Key:</strong> ${details.key}</p>`;
        if (details.value) html += `<p><strong>Value:</strong> ${details.value}</p>`;
        if (details.query) html += `<p><strong>Query:</strong> ${details.query}</p>`;
        if (details.response) html += `<p><strong>Response:</strong> ${details.response}</p>`;
        if (details.context) html += `<p><strong>Context:</strong> ${details.context}</p>`;
        if (details.selected_option) html += `<p><strong>Selected:</strong> ${details.selected_option}</p>`;
        if (details.message_count !== undefined) html += `<p><strong>Messages:</strong> ${details.message_count}</p>`;

        if (details.relationships && details.relationships.length > 0) {
            html += '<h5>Relationships</h5><ul>';
            for (const rel of details.relationships.slice(0, 10)) {
                html += `<li>${rel.node?.label || rel.node?.id} (${rel.relationship})</li>`;
            }
            html += '</ul>';
        }

        container.innerHTML = html;
    }

    function showBrainError(message) {
        const container = document.getElementById('brain-node-details');
        if (container) {
            container.innerHTML = `<p class="text-error">Failed to load: ${message}</p>`;
        }
    }

    // === Public API ===
    window.BrainMap = {
        init: initBrainMap,
        refresh: loadBrainData,
        zoomIn: () => zoom(1.2),
        zoomOut: () => zoom(0.8),
        reset: resetView,
    };

    // Auto-initialize if brain map page exists
    if (document.getElementById('brainmap-canvas')) {
        document.addEventListener('DOMContentLoaded', initBrainMap);
    }
})();
