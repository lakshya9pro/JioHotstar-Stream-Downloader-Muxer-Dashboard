import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)

# Helper function to strip XML namespaces for easier ElementTree queries
def strip_namespaces(xml_str):
    # Remove default xmlns
    xml_str = re.sub(r'\sxmlns="[^"]+"', '', xml_str, count=1)
    # Remove xmlns:xsi etc. declarations
    xml_str = re.sub(r'\sxmlns:\w+="[^"]+"', '', xml_str)
    return xml_str

# Parse MPD manifest content to extract video resolutions, audio languages, and subtitles
def parse_mpd(mpd_content):
    try:
        # Strip BOM and whitespace
        mpd_content = mpd_content.strip()
        if mpd_content.startswith('\ufeff'):
            mpd_content = mpd_content[1:]
        mpd_content = mpd_content.strip()

        xml_clean = strip_namespaces(mpd_content)
        root = ET.fromstring(xml_clean)
        
        adaptation_sets = root.findall('.//AdaptationSet')
        
        videos = []
        audios = []
        subtitles = []
        
        for inset in adaptation_sets:
            content_type = inset.get('contentType')
            mime_type = inset.get('mimeType')
            lang = inset.get('lang')
            
            # Check for Role subtitle
            is_subtitle = False
            role_el = inset.find('.//Role')
            if role_el is not None and role_el.get('value') == 'subtitle':
                is_subtitle = True
                
            # Subtitles
            if content_type == 'text' or mime_type == 'text/vtt' or is_subtitle:
                subtitle_lang = lang or 'en'
                subtitles.append(subtitle_lang)
            # Audio
            elif mime_type and mime_type.startswith('audio/'):
                audio_lang = lang or 'und'
                if audio_lang not in audios:
                    audios.append(audio_lang)
            # Video
            elif mime_type and mime_type.startswith('video/'):
                reps = inset.findall('.//Representation')
                for rep in reps:
                    width = rep.get('width')
                    height = rep.get('height')
                    rep_id = rep.get('id')
                    bw = rep.get('bandwidth')
                    if height:
                        videos.append({
                            'id': rep_id,
                            'height': int(height),
                            'width': int(width) if width else 0,
                            'bandwidth': int(bw) if bw else 0
                        })
        
        # Sort video representations by height descending, then bandwidth descending
        videos.sort(key=lambda x: (x['height'], x['bandwidth']), reverse=True)
        
        # Deduplicate video qualities (keep only the highest bandwidth representation for each height)
        unique_videos = []
        seen_heights = set()
        for v in videos:
            if v['height'] not in seen_heights:
                seen_heights.add(v['height'])
                unique_videos.append(v)
                
        return {
            'status': 'ok',
            'video_qualities': unique_videos,
            'audio_languages': sorted(list(set(audios))),
            'subtitles': sorted(list(set(subtitles)))
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

# Route to serve the main Web UI page
@app.route('/')
def index():
    return render_template('index.html')

# Route to save pasted headers into url.txt
@app.route('/save', methods=['POST'])
def save_headers():
    try:
        data = request.get_json()
        if not data or 'headers' not in data:
            return jsonify({'status': 'error', 'error': 'No data provided'}), 400
            
        headers_content = data['headers'].strip()
        if not headers_content:
            return jsonify({'status': 'error', 'error': 'Headers content is empty'}), 400
            
        # Write to url.txt
        with open('url.txt', 'w', encoding='utf-8') as f:
            f.write(headers_content)
            
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# Route to analyze headers and retrieve manifest parameters
@app.route('/analyze', methods=['POST'])
def analyze_stream():
    try:
        data = request.get_json()
        if not data or 'headers' not in data:
            return jsonify({'status': 'error', 'error': 'No data provided'}), 400
            
        headers_content = data['headers'].strip()
        # Clean BOM
        if headers_content.startswith('\ufeff'):
            headers_content = headers_content[1:]
        headers_content = headers_content.strip()
        
        if not headers_content:
            return jsonify({'status': 'error', 'error': 'Headers content is empty'}), 400
            
        # Write to url.txt
        with open('url.txt', 'w', encoding='utf-8') as f:
            f.write(headers_content)
            
        # Import parse utility from downloader script
        from download_hotstar import parse_url_file
        url, headers = parse_url_file('url.txt')
        
        # Check if direct XML was pasted
        if not url:
            if headers_content.startswith('<?xml') or '<MPD' in headers_content:
                parsed = parse_mpd(headers_content)
                if parsed['status'] == 'ok':
                    parsed['used_fallback'] = False
                    parsed['detected_url'] = 'Direct XML Input'
                    parsed['detected_cookie'] = False
                    parsed['detected_ua'] = 'N/A'
                    return jsonify(parsed)
            return jsonify({'status': 'error', 'error': 'Could not detect a video URL or valid MPD XML in the input.'}), 400
            
        xml_content = None
        
        # Try to fetch manifest content directly from target URL
        if url:
            clean_headers = {}
            for k, v in headers.items():
                # Avoid requesting compressed data to prevent raw binary response
                if not k.startswith(':') and k.lower() != 'accept-encoding':
                    clean_headers[k] = v
            
            try:
                import urllib.request
                import gzip
                import zlib
                
                req = urllib.request.Request(url)
                for k, v in clean_headers.items():
                    req.add_header(k, v)
                if 'User-Agent' not in req.headers and 'user-agent' not in req.headers:
                    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                with urllib.request.urlopen(req, timeout=8) as response:
                    content_encoding = response.info().get('Content-Encoding', '').lower()
                    raw_data = response.read()
                    
                    # Decompress if necessary
                    if 'gzip' in content_encoding:
                        raw_data = gzip.decompress(raw_data)
                    elif 'deflate' in content_encoding:
                        raw_data = zlib.decompress(raw_data)
                        
                    xml_content = raw_data.decode('utf-8', errors='ignore')
            except Exception as fetch_err:
                print(f"Direct manifest fetch failed: {fetch_err}")
                
        # If fetching failed, try the local fallback file 'New Text Document.txt'
        used_fallback = False
        if not xml_content:
            if os.path.exists('New Text Document.txt'):
                with open('New Text Document.txt', 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                used_fallback = True
                
        if not xml_content:
            return jsonify({
                'status': 'error', 
                'error': 'Failed to retrieve manifest content from URL, and no local fallback "New Text Document.txt" was found.'
            }), 400
            
        # Clean BOM and leading/trailing whitespace
        xml_content = xml_content.strip()
        if xml_content.startswith('\ufeff'):
            xml_content = xml_content[1:]
        xml_content = xml_content.strip()
        
        # Verify if the fetched document is actually XML
        if not xml_content.startswith('<'):
            snippet = xml_content[:200]
            return jsonify({
                'status': 'error',
                'error': f'Manifest response is not valid XML. It starts with:\n{snippet}'
            }), 400
            
        parsed = parse_mpd(xml_content)
        if parsed['status'] == 'ok':
            parsed['used_fallback'] = used_fallback
            parsed['detected_url'] = url
            parsed['detected_cookie'] = 'cookie' in headers
            parsed['detected_ua'] = headers.get('user-agent', 'Default')
            return jsonify(parsed)
        else:
            return jsonify({'status': 'error', 'error': f"Failed to parse manifest XML: {parsed.get('error')}"}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# Route to stream downloader execution log with parameters
@app.route('/download')
def download_stream():
    def generate():
        try:
            # Extract download configuration from query parameters
            quality = request.args.get('quality', 'best')
            audio_langs = request.args.get('audio_langs', '')
            sub_langs = request.args.get('sub_langs', '')
            mode = request.args.get('mode', 'mux')
            embed_subs = request.args.get('embed_subs', 'true')
            embed_metadata = request.args.get('embed_metadata', 'true')
            output_name = request.args.get('output_name', 'hotstar_video')

            # Launch download_hotstar.py using python -u (unbuffered) with args
            cmd_args = [
                sys.executable, '-u', 'download_hotstar.py',
                '--quality', quality,
                '--audio-langs', audio_langs,
                '--sub-langs', sub_langs,
                '--mode', mode,
                '--embed-subs', embed_subs,
                '--embed-metadata', embed_metadata,
                '--output-name', output_name
            ]
            
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd()
            )
            
            # Read stdout line by line and stream it to the Web UI
            for line in iter(process.stdout.readline, ''):
                clean_line = line.replace('\r', '').replace('\n', '')
                yield f"data: {clean_line}\n\n"
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code == 0:
                yield "data: [DONE]\n\n"
            else:
                yield f"data: [ERROR] Downloader process exited with code {return_code}\n\n"
                
        except Exception as e:
            yield f"data: [ERROR] Failed to run script: {str(e)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    # Start the local server
    print("--------------------------------------------------")
    print("Hotstar Stream Downloader Server is starting...")
    print("Open http://127.0.0.1:5000 in your browser.")
    print("--------------------------------------------------")
    app.run(host='127.0.0.1', port=5000, debug=False)
