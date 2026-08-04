import os

def search_knowledge(user_message):

    base_path = "knowledge"

    if not os.path.exists(base_path):
        return None

    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in {"txt_disabled", "disabled"}]

        for file in files:
            if not file.endswith(".txt"):
                continue

            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                    if user_message.lower() in content.lower():
                        return content[:800]
            except:
                continue

    return None
