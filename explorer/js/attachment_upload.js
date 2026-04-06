async function handleBlob(blob, ext, show_link=true) {
    const formData = new FormData();
    // date-based fallback for crypto.randomUUID for http local instances - follow the expected format of upload_attachment_
    const imageid = crypto.randomUUID ? crypto.randomUUID() :
        'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
    const prefix = show_link ? 'pasted_image' : 'last_output';
    const filename = `${prefix}_${imageid}.${ext}`;
    const msgid = htmx.find('#full_editor input[name="msgid"]').value || '';
    const msg_type = htmx.find('#msg_type').value || '';
    let dlg_name = document.getElementById('dlg_name').value;
    formData.append('file', new File([blob], filename, {type: blob.type}));
    formData.append('msgid', msgid);
    formData.append('msg_type', msg_type);
    formData.append('dlg_name', dlg_name);

    const r = await fetch('/upload_attachment_', {method: 'POST', body: formData});
    if (r.status !== 200) {console.log('upload failed', r); return}

    let data;
    try {
        const responseText = await r.text();
        data = JSON.parse(responseText);
    } catch (e) {
        console.log('JSON parse error: response was not valid JSON', responseText);
        return;
    }

    // when uploading an attachment we need to link it to a message.
    // if `msgid` is undefined we create an empty message in the db and return the stable message id (`data.id`).
    // we set the editor's msgid to `data.id` so that when the user hits submit any changes are saved this message.
    htmx.find('#full_editor input[name="msgid"]').value = data.id;
    const markdown_link = show_link ? `\n![${filename}](attachment:${imageid})\n` : `<!-- last_output:${imageid} -->\n`;
    if (window.editor && editor.getModel()) {
        const model = editor.getModel();
        const fullContent = model.getValue();
        if (!show_link) {
            const pattern = /<!-- last_output:[0-9a-f-]{36} -->/;
            if (pattern.test(fullContent)) {
                const newContent = fullContent.replace(pattern, markdown_link.trim());
                model.setValue(newContent);
                return;
            }
        }
        const position = editor.getPosition();
        editor.executeEdits('paste-image', [{
            range: {
                startLineNumber: position.lineNumber,
                startColumn: position.column,
                endLineNumber: position.lineNumber,
                endColumn: position.column
            },
            text: markdown_link
        }]);
    }
}

window.pasteHandledElements = window.pasteHandledElements || new WeakSet();
window.pasteHandler = window.pasteHandler || async function(e) {
    const imageItem = Array.from(e.clipboardData.items).find(item => item.type.startsWith('image'));
    if (imageItem) {
        const blob = imageItem.getAsFile();
        await handleBlob(blob, imageItem.type.split('/')[1] || 'png');
    }
};

htmx.onLoad(() => {
    // Attach paste handler to body if not already attached
    const zone = document.body;
    if (zone && !window.pasteHandledElements.has(zone)) {
        zone.addEventListener('paste', window.pasteHandler, true); 
        window.pasteHandledElements.add(zone);
    }
})

async function captureElement(element) {
  if (!("CropTarget" in window)) {
    console.error("Region Capture API is not supported in this browser.");
    return null;
  }
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({ preferCurrentTab: true, cursor: 'never' });
    const [track] = stream.getVideoTracks();
    const cropTarget = await CropTarget.fromElement(element);
    await track.cropTo(cropTarget);
    const bitmap = await new ImageCapture(track).grabFrame();
    track.stop();
    const canvas = document.createElement('canvas');
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    canvas.getContext('2d').drawImage(bitmap, 0, 0);
    return canvas.toDataURL('image/png'); // Return the image as a WebP data URL.
  } catch (error) {
    console.error(`Region Capture Failed: ${error.name}`, error);
    return null;
  }
};

