def admin_bar_html():
    return """
    <script>document.body.classList.add("has-admin-bar");</script>
    <div class="admin-bar">
        <div class="admin-bar-inner">
            <a class="admin-brand" href="/">定承資訊AI客服管理後台</a>
            <div class="admin-actions">
                <a class="admin-identity" href="/admin/users" title="帳號管理">
                    <span class="admin-avatar" aria-hidden="true">人</span>
                    <b id="admin-name">管理員</b>
                </a>
                <a class="admin-logout" href="/logout">登出</a>
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

    body.dark .admin-bar {
        background:rgba(22,32,51,0.94);
    }

    body.has-admin-bar {
        padding-top:76px !important;
    }

    .admin-bar-inner {
        width:100%;
        min-height:52px;
        margin:0 auto;
        padding:8px 24px;
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
    }

    .admin-actions {
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
    }

    .admin-logout {
        min-height:28px;
        padding:5px 11px;
        border-radius:999px;
        border:1px solid var(--border);
        background:var(--panel-soft);
        color:var(--text);
    }

    @media (max-width:860px) {
        body.has-admin-bar {
            padding-top:92px !important;
        }

        .admin-bar-inner {
            min-height:68px;
            padding:10px 14px;
            align-items:stretch;
            gap:8px;
        }

        .admin-brand {
            font-size:14px;
        }

        .admin-actions {
            justify-content:space-between;
        }
    }
    """
