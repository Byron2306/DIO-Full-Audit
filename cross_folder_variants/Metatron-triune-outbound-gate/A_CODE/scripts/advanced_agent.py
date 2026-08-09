"""Compatibility surface for legacy advanced-agent credential tests.

The operational endpoint agent now lives in ``unified_agent/core/agent.py``.
This module keeps the old credential-theft detector import contract available
for tests and migration tooling without reintroducing the legacy mini-agent.
"""


class CredentialTheftDetector:
    CREDENTIAL_THEFT_TOOLS = {
        "mimikatz", "mimikatz.exe", "sekurlsa", "procdump", "procdump.exe",
        "nanodump", "nanodump.exe", "comsvcs.dll", "rundll32.exe",
        "lsassy", "lazagne", "lazagne.exe", "pwdump", "fgdump",
        "gsecdump", "wce", "wce.exe", "creddump", "secretsdump.py",
        "pypykatz", "hashcat", "john", "john.exe", "hydra", "medusa",
        "ncrack", "kerbrute", "rubeus", "rubeus.exe", "seatbelt",
        "sharpdump", "sharpdpapi", "sharpchrome", "browserghost",
        "mimipenguin", "linpeas", "winpeas", "trufflehog", "gitleaks",
        "cloudfox", "pacumen", "adfind", "bloodhound", "sharphound",
    }

    WINDOWS_CREDENTIAL_PATHS = [
        r"C:\\Windows\\System32\\config\\SAM",
        r"C:\\Windows\\System32\\config\\SECURITY",
        r"C:\\Users\\*\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data",
        r"C:\\Users\\*\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles\\*\\logins.json",
        r"C:\\Users\\*\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Login Data",
    ]
    LINUX_CREDENTIAL_PATHS = [
        "/etc/shadow",
        "/etc/passwd",
        "~/.ssh/id_rsa",
        "~/.ssh/authorized_keys",
        "~/.aws/credentials",
        "~/.config/google-chrome/Default/Login Data",
        "~/.mozilla/firefox/*/logins.json",
    ]
    MACOS_CREDENTIAL_PATHS = [
        "~/Library/Keychains/login.keychain-db",
        "~/Library/Application Support/Google/Chrome/Default/Login Data",
        "~/Library/Application Support/Firefox/Profiles/*/logins.json",
    ]
    LSASS_ACCESS_PATTERNS = [
        "lsass",
        "lsass.exe",
        "MiniDumpWriteDump",
        "comsvcs.dll",
        "process dump",
    ]


def main():
    """CLI placeholder: supports --credential-scan / credential_scan."""
    return {"credential_scan": True}


if __name__ == "__main__":
    main()
