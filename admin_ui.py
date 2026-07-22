def admin_bar_html():
    return """
    <script>
    (function(){
        var styleTheme = localStorage.getItem("admin-style-theme") || "console";
        document.documentElement.classList.add("style-" + styleTheme);
        if(document.body){
            document.body.classList.add("style-" + styleTheme);
        }
    })();
    document.body.classList.add("has-admin-bar");
    </script>
    <div class="admin-bar">
        <div class="admin-bar-inner">
            <a class="admin-brand" href="/">
                <img src="/static/admin-logo.png" alt="">
                <span>定承資訊AI客服管理後台</span>
            </a>
            <nav class="admin-nav-menu" aria-label="後台導覽">
                <a class="admin-nav-link" data-path="/" href="/">Dashboard</a>
                <a class="admin-nav-link" data-path="/logs" href="/logs">LOGS</a>
                <a class="admin-nav-link" data-path="/faq" href="/faq">知識管理</a>
                <a class="admin-nav-link" data-path="/test-chat" href="/test-chat">測試</a>
                <a class="admin-nav-link" data-path="/admin/users" href="/admin/users">帳號管理</a>
            </nav>
            <div class="admin-actions">
                <a class="admin-identity" href="/admin/users" title="帳號管理">
                    <span class="admin-avatar" id="admin-avatar" aria-hidden="true">管</span>
                    <b id="admin-name">管理員</b>
                </a>
                <button type="button" class="admin-menu-toggle" id="admin-menu-toggle" aria-label="開啟導覽選單" aria-expanded="false">☰</button>
                <a class="admin-logout" href="/logout">登出</a>
                <div class="admin-font-controls" aria-label="文字大小">
                    <button type="button" id="admin-font-down" title="縮小文字">A-</button>
                    <button type="button" id="admin-font-reset" title="恢復正常文字">正常</button>
                    <button type="button" id="admin-font-up" title="放大文字">A+</button>
                </div>
                <label class="admin-theme-control" title="切換深夜模式">
                    <span>深夜模式</span>
                    <span class="admin-switch">
                        <input id="admin-theme-toggle" type="checkbox">
                        <span class="admin-slider"></span>
                    </span>
                </label>
            </div>
        </div>
    </div>
    <script>
    (function(){
        function cookieValue(name){
            var items = document.cookie ? document.cookie.split(";") : [];
            for(var i = 0; i < items.length; i++){
                var item = items[i].trim();
                if(item.indexOf(name + "=") === 0){
                    var value = item.substring(name.length + 1);
                    if(value.length >= 2 && value.charAt(0) === '"' && value.charAt(value.length - 1) === '"'){
                        value = value.substring(1, value.length - 1);
                    }
                    return decodeURIComponent(value);
                }
            }
            return "";
        }
        var display = cookieValue("admin_display") || "管理員";
        var target = document.getElementById("admin-name");
        var avatar = document.getElementById("admin-avatar");
        if(target){
            target.textContent = display;
        }
        if(avatar){
            avatar.textContent = display.trim().charAt(0).toUpperCase() || "管";
        }

        var path = window.location.pathname || "/";
        document.querySelectorAll(".admin-nav-link").forEach(function(link){
            var target = link.getAttribute("data-path") || "/";
            var active = target === "/" ? path === "/" : path.indexOf(target) === 0;
            link.classList.toggle("active", active);
        });

        var themeToggle = document.getElementById("admin-theme-toggle");
        var styleTheme = localStorage.getItem("admin-style-theme") || "console";
        document.body.classList.remove("style-light", "style-console");
        document.body.classList.add("style-" + styleTheme);
        var storedTheme = localStorage.getItem("admin-theme")
            || localStorage.getItem("dashboard-theme")
            || localStorage.getItem("logs-theme")
            || localStorage.getItem("faq-theme")
            || localStorage.getItem("test-theme")
            || "light";

        function applyTheme(isDark){
            document.body.classList.toggle("dark", isDark);
            if(themeToggle){
                themeToggle.checked = isDark;
            }
            var value = isDark ? "dark" : "light";
            ["admin-theme", "dashboard-theme", "logs-theme", "faq-theme", "test-theme"].forEach(function(key){
                localStorage.setItem(key, value);
            });
        }

        applyTheme(storedTheme === "dark");

        if(themeToggle){
            themeToggle.addEventListener("change", function(){
                applyTheme(themeToggle.checked);
            });
        }

        var fontSteps = ["sm", "normal", "lg", "xl"];
        var fontLabels = {"sm":"小", "normal":"正常", "lg":"大", "xl":"特大"};
        var storedFont = localStorage.getItem("admin-font-size") || "normal";

        function applyFontSize(value){
            if(fontSteps.indexOf(value) === -1){
                value = "normal";
            }
            document.body.classList.remove("admin-font-sm", "admin-font-normal", "admin-font-lg", "admin-font-xl");
            document.body.classList.add("admin-font-" + value);
            localStorage.setItem("admin-font-size", value);
            var reset = document.getElementById("admin-font-reset");
            if(reset){
                reset.setAttribute("title", "目前文字大小：" + (fontLabels[value] || "正常") + "，點擊恢復正常");
            }
        }

        function changeFontSize(delta){
            var current = localStorage.getItem("admin-font-size") || "normal";
            var index = fontSteps.indexOf(current);
            if(index === -1){
                index = 1;
            }
            var next = fontSteps[Math.max(0, Math.min(fontSteps.length - 1, index + delta))];
            applyFontSize(next);
        }

        applyFontSize(storedFont);

        var fontDown = document.getElementById("admin-font-down");
        var fontUp = document.getElementById("admin-font-up");
        var fontReset = document.getElementById("admin-font-reset");
        if(fontDown){
            fontDown.addEventListener("click", function(){ changeFontSize(-1); });
        }
        if(fontUp){
            fontUp.addEventListener("click", function(){ changeFontSize(1); });
        }
        if(fontReset){
            fontReset.addEventListener("click", function(){ applyFontSize("normal"); });
        }

        var menuToggle = document.getElementById("admin-menu-toggle");
        var adminBar = document.querySelector(".admin-bar");
        if(menuToggle && adminBar){
            menuToggle.addEventListener("click", function(){
                var open = adminBar.classList.toggle("menu-open");
                document.body.classList.toggle("admin-menu-open", open);
                menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
            });
            document.querySelectorAll(".admin-nav-link").forEach(function(link){
                link.addEventListener("click", function(){
                    adminBar.classList.remove("menu-open");
                    document.body.classList.remove("admin-menu-open");
                    menuToggle.setAttribute("aria-expanded", "false");
                });
            });
        }
    })();
    </script>
    """


def admin_bar_css():
    return """
    html.dark body {
        --bg:#0f172a;
        --panel:#162033;
        --panel-soft:#1e293b;
        --text:#e5edf7;
        --muted:#94a3b8;
        --border:#334155;
        --shadow:0 16px 40px rgba(0,0,0,0.28);
    }

    .admin-bar {
        position:fixed;
        top:0;
        left:0;
        right:0;
        z-index:1000;
        width:100%;
        margin:0;
        border-bottom:1px solid var(--border);
        background:rgba(255,255,255,0.94);
        backdrop-filter:blur(14px);
        box-shadow:0 10px 28px rgba(15,23,42,0.08);
    }

    body.dark .admin-bar,
    html.dark body .admin-bar {
        background:rgba(22,32,51,0.94);
    }

    body.has-admin-bar {
        padding-top:82px !important;
    }

    body.has-admin-bar main.page > nav.nav,
    body.has-admin-bar .topbar .theme-control {
        display:none !important;
    }

    body.admin-font-sm main.page {
        zoom:0.94;
        font-size:15px;
    }

    body.admin-font-normal main.page {
        zoom:1;
    }

    body.admin-font-lg main.page {
        zoom:1.08;
        font-size:17px;
    }

    body.admin-font-xl main.page {
        zoom:1.16;
        font-size:18px;
    }

    html.style-console body,
    body.style-console {
        --bg:#f5f6f8;
        --panel:#ffffff;
        --panel-soft:#eef1f4;
        --text:#172033;
        --muted:#5b6778;
        --border:#cfd8e3;
        --button-bg:#1f4f7a;
        --button-bg-hover:#173d61;
        --accent:#1f4f7a;
        --accent-strong:#173d61;
        --accent-soft:#e5edf5;
        --shadow:none;
        background:var(--bg) !important;
    }

    html.style-console body.dark,
    body.dark.style-console {
        --bg:#0f151c;
        --panel:#17212c;
        --panel-soft:#202c38;
        --text:#e6edf3;
        --muted:#9aa8b8;
        --border:#2f3d4c;
        --button-bg:#2f6f9f;
        --button-bg-hover:#3b82b8;
        --accent:#67a7d8;
        --accent-strong:#9fd0f2;
        --accent-soft:rgba(103,167,216,0.14);
        --shadow:none;
        background:var(--bg) !important;
    }

    html.style-console body .page,
    body.style-console .page {
        max-width:1400px;
    }

    html.style-console body .topbar,
    body.style-console .topbar {
        border-bottom:1px solid var(--border);
        padding-bottom:12px;
        margin-bottom:16px;
    }

    html.style-console body h1,
    body.style-console h1 {
        font-size:28px;
        line-height:1.25;
        letter-spacing:0;
    }

    html.style-console body h2,
    body.style-console h2 {
        font-size:22px;
        line-height:1.3;
        letter-spacing:0;
    }

    html.style-console body h3,
    body.style-console h3 {
        font-size:17px;
        line-height:1.35;
    }

    html.style-console body .card,
    body.style-console .card,
    html.style-console body .metric-card,
    body.style-console .metric-card,
    html.style-console body .report-box,
    body.style-console .report-box,
    html.style-console body .bar,
    body.style-console .bar,
    html.style-console body .table-wrap,
    body.style-console .table-wrap,
    html.style-console body .admin-card,
    body.style-console .admin-card,
    html.style-console body .admin-tool-card,
    body.style-console .admin-tool-card,
    html.style-console body .notice-card,
    body.style-console .notice-card,
    html.style-console body .summary-card,
    body.style-console .summary-card,
    html.style-console body .filter-card,
    body.style-console .filter-card,
    html.style-console body .modal-content,
    body.style-console .modal-content,
    html.style-console body .drawer-panel,
    body.style-console .drawer-panel,
    html.style-console body .detail-panel,
    body.style-console .detail-panel {
        border-radius:4px !important;
        box-shadow:none !important;
        border-color:var(--border) !important;
    }

    html.style-console body .card,
    body.style-console .card,
    html.style-console body .admin-tool-card,
    body.style-console .admin-tool-card {
        padding:14px !important;
    }

    html.style-console body .admin-card,
    body.style-console .admin-card,
    html.style-console body .table-wrap,
    body.style-console .table-wrap {
        padding:0 !important;
        overflow:hidden;
    }

    html.style-console body .section-heading,
    body.style-console .section-heading {
        padding:14px 42px 12px 16px;
        background:var(--panel);
    }

    html.style-console body .tool-heading,
    body.style-console .tool-heading {
        margin-bottom:12px;
    }

    html.style-console body .metric-card,
    body.style-console .metric-card {
        min-height:96px;
        padding:14px !important;
    }

    html.style-console body .metric-card strong,
    body.style-console .metric-card strong {
        font-size:28px;
        letter-spacing:0;
    }

    html.style-console body table,
    body.style-console table {
        border-collapse:collapse;
    }

    html.style-console body th,
    body.style-console th {
        background:#edf2f7 !important;
        color:#526173 !important;
        font-size:13px;
        font-weight:800;
        padding:10px 12px;
        border-top:0;
        border-bottom:1px solid var(--border);
    }

    html.style-console body.dark th,
    body.dark.style-console th {
        background:#202c38 !important;
        color:#a8b6c6 !important;
    }

    html.style-console body td,
    body.style-console td {
        padding:10px 12px;
        border-top:1px solid var(--border);
        vertical-align:middle;
    }

    html.style-console body button:not(.theme-option),
    body.style-console button:not(.theme-option),
    html.style-console body .nav-link.active,
    body.style-console .nav-link.active,
    html.style-console body .btn-edit,
    body.style-console .btn-edit,
    html.style-console body .export-link,
    body.style-console .export-link {
        background:var(--button-bg) !important;
        color:#ffffff !important;
        border-color:transparent !important;
        box-shadow:none !important;
        border-radius:4px !important;
        min-height:34px;
        font-size:13px;
        font-weight:800;
    }

    html.style-console body a[class*="btn"],
    body.style-console a[class*="btn"],
    html.style-console body .export-link,
    body.style-console .export-link,
    html.style-console body .faq-transfer-btn,
    body.style-console .faq-transfer-btn,
    html.style-console body .disabled-btn,
    body.style-console .disabled-btn {
        border-radius:4px !important;
        box-shadow:none !important;
    }

    html.style-console body .disabled-btn,
    body.style-console .disabled-btn {
        background:var(--panel-soft) !important;
        color:var(--muted) !important;
        border:1px solid var(--border) !important;
    }

    html.style-console body .admin-nav-link.active,
    body.style-console .admin-nav-link.active {
        background:transparent !important;
        color:var(--text) !important;
        box-shadow:none !important;
    }

    html.style-console body .admin-nav-link.active::after,
    body.style-console .admin-nav-link.active::after {
        background:var(--button-bg) !important;
    }

    html.style-console body .clear-link,
    body.style-console .clear-link {
        background:#dc2626 !important;
        color:#ffffff !important;
    }

    html.style-console body .quality-warn,
    body.style-console .quality-warn,
    html.style-console body .btn-toggle,
    body.style-console .btn-toggle {
        background:#b7791f !important;
        color:#ffffff !important;
    }

    html.style-console body .quality-danger,
    body.style-console .quality-danger,
    html.style-console body .btn-del,
    body.style-console .btn-del,
    html.style-console body .delete-btn,
    body.style-console .delete-btn {
        background:#b91c1c !important;
        color:#ffffff !important;
    }

    html.style-console body .btn-toggle.toggle-on,
    body.style-console .btn-toggle.toggle-on {
        background:#047857 !important;
        color:#ffffff !important;
    }

    html.style-console body .faq-added-pill,
    body.style-console .faq-added-pill,
    html.style-console body .quality-pill,
    body.style-console .quality-pill,
    html.style-console body .status-pill,
    body.style-console .status-pill,
    html.style-console body .role-pill,
    body.style-console .role-pill,
    html.style-console body .quick-chip,
    body.style-console .quick-chip,
    html.style-console body .tab,
    body.style-console .tab,
    html.style-console body .badge,
    body.style-console .badge,
    html.style-console body .lead-badge,
    body.style-console .lead-badge {
        border-radius:4px !important;
        box-shadow:none !important;
        background:var(--accent-soft);
    }

    html.style-console body button:not(.theme-option):hover,
    body.style-console button:not(.theme-option):hover {
        background:var(--button-bg-hover) !important;
    }

    html.style-console body .admin-bar,
    body.style-console .admin-bar {
        background:#ffffff;
        backdrop-filter:none;
        box-shadow:none;
    }

    html.style-console body.dark .admin-bar,
    body.dark.style-console .admin-bar {
        background:#17212c;
        backdrop-filter:none;
    }

    html.style-console body .admin-avatar,
    body.style-console .admin-avatar {
        background:var(--button-bg);
        border-radius:4px;
        box-shadow:none;
    }

    html.style-console body .nav-link,
    body.style-console .nav-link,
    html.style-console body .admin-nav-link,
    body.style-console .admin-nav-link,
    html.style-console body input,
    body.style-console input,
    html.style-console body select,
    body.style-console select,
    html.style-console body textarea,
    body.style-console textarea {
        border-radius:4px !important;
        box-shadow:none !important;
    }

    html.style-console body input,
    body.style-console input,
    html.style-console body select,
    body.style-console select,
    html.style-console body textarea,
    body.style-console textarea {
        background:var(--panel);
        border-color:var(--border);
    }

    html.style-console body .admin-font-controls,
    body.style-console .admin-font-controls,
    html.style-console body .admin-logout,
    body.style-console .admin-logout,
    html.style-console body .admin-menu-toggle,
    body.style-console .admin-menu-toggle {
        border-radius:4px;
        box-shadow:none;
    }

    html.style-console body .admin-switch,
    body.style-console .admin-switch,
    html.style-console body .admin-slider,
    body.style-console .admin-slider {
        border-radius:4px;
    }

    html.style-console body .admin-slider::before,
    body.style-console .admin-slider::before {
        border-radius:3px;
    }

    .admin-bar-inner {
        width:100%;
        min-height:58px;
        margin:0 auto;
        padding:8px 18px;
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
    }

    .admin-brand {
        color:var(--text);
        text-decoration:none;
        font-size:15px;
        font-weight:900;
        letter-spacing:0;
        white-space:nowrap;
        display:inline-flex;
        align-items:center;
        gap:8px;
        min-width:max-content;
    }

    .admin-brand img {
        width:24px;
        height:24px;
        border-radius:6px;
        object-fit:contain;
    }

    .admin-nav-menu {
        flex:1 1 auto;
        display:flex;
        align-items:center;
        justify-content:center;
        gap:2px;
        min-width:0;
    }

    .admin-nav-link {
        position:relative;
        min-height:42px;
        padding:10px 13px;
        border-radius:0;
        color:var(--muted);
        text-decoration:none;
        font-size:13px;
        font-weight:800;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        white-space:nowrap;
    }

    .admin-nav-link::after {
        content:"";
        position:absolute;
        left:10px;
        right:10px;
        bottom:4px;
        height:3px;
        background:transparent;
        transition:background 0.18s ease;
    }

    .admin-nav-link:hover {
        color:var(--text);
        background:var(--panel-soft);
    }

    .admin-nav-link.active {
        color:var(--text);
        background:transparent;
        box-shadow:none;
    }

    .admin-nav-link.active::after {
        background:linear-gradient(135deg,#60a5fa,#a78bfa);
    }

    .admin-actions {
        flex:0 0 auto;
        display:flex;
        align-items:center;
        gap:10px;
    }

    .admin-identity,
    .admin-logout {
        color:var(--text);
        text-decoration:none;
        font-size:13px;
        font-weight:800;
        display:inline-flex;
        align-items:center;
        gap:8px;
    }

    .admin-identity b {
        color:var(--text);
    }

    .admin-font-controls {
        display:inline-flex;
        align-items:center;
        gap:2px;
        padding:2px;
        border:1px solid var(--border);
        border-radius:999px;
        background:var(--panel-soft);
    }

    .admin-font-controls button {
        min-width:30px;
        min-height:28px;
        padding:4px 8px;
        border:0;
        border-radius:999px;
        background:transparent;
        color:var(--muted);
        font-size:12px;
        font-weight:900;
        cursor:pointer;
        line-height:1;
    }

    .admin-font-controls button:hover {
        background:var(--panel);
        color:var(--text);
    }

    #admin-font-reset {
        min-width:42px;
    }

    .admin-avatar {
        width:28px;
        height:28px;
        border-radius:50%;
        background:linear-gradient(135deg,#60a5fa,#a78bfa);
        color:white;
        font-size:12px;
        font-weight:900;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        box-shadow:0 8px 18px rgba(79,70,229,0.22);
        line-height:1;
    }

    .admin-logout {
        min-height:28px;
        padding:5px 11px;
        border-radius:999px;
        border:1px solid var(--border);
        background:var(--panel-soft);
        color:var(--text);
    }

    .admin-menu-toggle {
        display:none;
        width:34px;
        height:34px;
        min-width:34px;
        min-height:34px;
        padding:0;
        border-radius:8px;
        border:1px solid var(--border);
        background:var(--panel-soft);
        color:var(--text);
        font-size:18px;
        font-weight:900;
        align-items:center;
        justify-content:center;
        cursor:pointer;
    }

    .admin-theme-control {
        flex:0 0 auto;
        display:flex;
        align-items:center;
        gap:8px;
        color:var(--muted);
        font-size:13px;
        font-weight:800;
        cursor:pointer;
        user-select:none;
    }

    .admin-switch {
        position:relative;
        width:46px;
        height:26px;
        flex:0 0 auto;
    }

    .admin-switch input {
        position:absolute;
        opacity:0;
        width:0;
        height:0;
    }

    .admin-slider {
        position:absolute;
        inset:0;
        border-radius:999px;
        background:#cbd5e1;
        transition:background 0.2s ease;
        box-shadow:inset 0 1px 3px rgba(15,23,42,0.18);
    }

    .admin-slider::before {
        content:"";
        position:absolute;
        width:22px;
        height:22px;
        left:2px;
        top:2px;
        border-radius:50%;
        background:#fff;
        box-shadow:0 2px 8px rgba(15,23,42,0.25);
        transition:transform 0.2s ease;
    }

    .admin-switch input:checked + .admin-slider {
        background:linear-gradient(135deg,#60a5fa,#a78bfa);
    }

    .admin-switch input:checked + .admin-slider::before {
        transform:translateX(20px);
    }

    @media (max-width:860px) {
        body.has-admin-bar {
            padding-top:74px !important;
        }

        .admin-bar-inner {
            min-height:58px;
            padding:10px 14px;
            align-items:center;
            flex-direction:row;
            flex-wrap:wrap;
            gap:8px;
        }

        .admin-brand {
            font-size:14px;
            flex:1 1 0;
            min-width:0;
        }

        .admin-brand span {
            overflow:hidden;
            text-overflow:ellipsis;
            white-space:nowrap;
        }

        .admin-actions {
            flex:0 0 auto;
            justify-content:flex-end;
            gap:8px;
            min-width:0;
            order:1;
        }

        .admin-menu-toggle {
            display:inline-flex;
            order:2;
        }

        .admin-nav-menu {
            display:none;
            flex:1 1 100%;
            order:3;
            grid-template-columns:1fr;
            gap:0;
            padding-top:8px;
            border-top:1px solid var(--border);
        }

        .admin-bar.menu-open .admin-nav-menu {
            display:grid;
        }

        body.admin-menu-open.has-admin-bar {
            padding-top:260px !important;
        }

        .admin-nav-link {
            width:100%;
            min-height:38px;
            padding:10px 8px 10px 14px;
            font-size:12px;
            justify-content:flex-start;
            border-bottom:1px solid var(--border);
        }

        .admin-nav-link::after {
            left:0;
            right:auto;
            top:9px;
            bottom:9px;
            width:3px;
            height:auto;
        }

        .admin-theme-control span:first-child {
            display:none;
        }

        .admin-font-controls {
            order:3;
        }

        .admin-font-controls button {
            min-width:28px;
            padding:4px 7px;
        }

        #admin-font-reset {
            min-width:36px;
        }

        .admin-identity b {
            max-width:92px;
            overflow:hidden;
            text-overflow:ellipsis;
            white-space:nowrap;
        }

        .admin-logout {
            padding:5px 9px;
        }

        .admin-theme-control {
            gap:0;
        }
    }

    @media (max-width:520px) {
        .admin-brand span {
            max-width:42vw;
        }

        .admin-identity b {
            max-width:72px;
        }

        .admin-logout {
            min-width:0;
            padding:5px 8px;
        }

        .admin-actions {
            gap:6px;
        }

        .admin-font-controls {
            flex:1 1 100%;
            justify-content:center;
            order:5;
        }
    }
    """
