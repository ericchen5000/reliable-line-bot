import html


def admin_bar_html():
    return """
    <div class="admin-bar">
        <div class="admin-bar-inner">
            <a class="admin-identity" href="/admin/users">
                <span class="admin-dot"></span>
                <span>管理者：</span><b id="admin-name">-</b>
            </a>
            <a class="admin-logout" href="/logout">登出</a>
        </div>
    </div>
    <script>
    (function(){
        function cookieValue(name){
            var items = document.cookie ? document.cookie.split(";") : [];
            for(var i = 0; i < items.length; i++){
                var item = items[i].trim();
                if(item.indexOf(name + "=") === 0){
                    return decodeURIComponent(item.substring(name.length + 1));
                }
            }
            return "";
        }
        var target = document.getElementById("admin-name");
        if(target){
            target.textContent = cookieValue("admin_display") || "管理員";
        }
    })();
    </script>
    """


def admin_bar_css():
    return """
    .admin-bar {
        width:100%;
        margin:0 0 18px;
    }

    .admin-bar-inner {
        max-width:1280px;
        min-height:40px;
        margin:0 auto;
        padding:8px 12px;
        border:1px solid var(--border);
        border-radius:8px;
        background:var(--panel);
        box-shadow:0 10px 24px rgba(15,23,42,0.05);
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
    }

    .admin-identity,
    .admin-logout {
        color:var(--muted);
        text-decoration:none;
        font-size:13px;
        font-weight:700;
        display:inline-flex;
        align-items:center;
        gap:6px;
    }

    .admin-identity b {
        color:var(--text);
    }

    .admin-dot {
        width:8px;
        height:8px;
        border-radius:50%;
        background:#22c55e;
        box-shadow:0 0 0 4px rgba(34,197,94,0.12);
    }

    .admin-logout {
        min-height:28px;
        padding:4px 10px;
        border-radius:999px;
        border:1px solid var(--border);
        background:var(--panel-soft);
        color:var(--text);
    }

    @media (max-width:860px) {
        .admin-bar {
            margin-bottom:14px;
        }

        .admin-bar-inner {
            align-items:flex-start;
            flex-direction:column;
        }

        .admin-logout {
            width:100%;
            justify-content:center;
        }
    }
    """


def admin_display_cookie(username):
    return html.escape(str(username or "管理員"), quote=False)
