import requests
import socket
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse

def display_logo():
    logo = """
   ______________      ___         ___             __    
  / __/_  __/ __ \____/ _ \___ ___/ (_)______ ____/ /____
 _\ \  / / / /_/ /___/ , _/ -_) _  / / __/ -_) __/ __(_-<
/___/ /_/  \____/   /_/|_|\__/\_,_/_/_/  \__/\__/\__/___/                                                                                                                                     
    """
    print(logo)
    print("Gets urls similarly to httpx and checks if there's any HTTP redirections to non-existant domains or inaccessible servers\n")



def normalize_https_redirect(url):
    """Convert HTTPS redirects with port 443 to standard HTTPS without port."""
    parsed_url = urlparse(url)
    if parsed_url.scheme == 'https' and parsed_url.port == 443:
        parsed_url = parsed_url._replace(netloc=parsed_url.hostname)
    return urlunparse(parsed_url)

def check_redirection(url):
    if not url.startswith(('http://', 'https://')):
        urls_to_check = [f"http://{url}", f"https://{url}"]
    else:
        urls_to_check = [url]

    for test_url in urls_to_check:
        try:
            response = requests.get(test_url, allow_redirects=False, timeout=1)
            if response.status_code in [301, 302, 307, 308]:
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    redirect_url = normalize_https_redirect(redirect_url)
                    original_domain = urlparse(test_url).netloc
                    redirect_domain = urlparse(redirect_url).netloc

                    # Skip if the redirection points to the same domain - we are looking for redirections to different origins.
                    if original_domain == redirect_domain:
                        break
                    
                    domain = urlparse(redirect_url).hostname
                    try:
                        socket.gethostbyname(domain)
                    except socket.gaierror:
                        return f"[FOUND] {url} redirected to unreachable domain '{domain}'"

                    try:
                        redirect_response = requests.get(redirect_url, timeout=1)
                        if redirect_response.status_code == 404:
                            return f"[FOUND] {url} Redirects to -> {redirect_url} | Result: 404 Not Found"
                    except requests.ConnectionError:
                        return f"[FOUND] {url} Redirects to -> {redirect_url} | Result: No Response"
                    except requests.RequestException:
                        return f"[FOUND] {url} Redirects to -> {redirect_url} | Result: Connection Failed"
            break
        except requests.RequestException:
            break
    return None

if __name__ == "__main__":
    display_logo()

    parser = argparse.ArgumentParser(description="Check redirection URLs in parallel.")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of concurrent threads to use.")
    args = parser.parse_args()

    targets = [line.strip() for line in sys.stdin]

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_url = {executor.submit(check_redirection, url): url for url in targets}
        for future in as_completed(future_to_url):
            try:
                result = future.result()
                if result:
                    print(result)
            except Exception as e:
                url = future_to_url[future]
                print(f"[ERROR] Unexpected error on {url}")
