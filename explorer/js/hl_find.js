function highLight(query, el, isRegex=false, useCase=false) {
  let walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);

  // Collect all text nodes
  let nodes=[], texts=[], node;
  while(node = walker.nextNode()) { nodes.push(node); texts.push(node.textContent); }

  // Find all match positions
  let txt = texts.join(''), matches = [], idx = 0;
  if(!isRegex) query = RegExp.escape(query);
  let flags = 'g';
  if(!useCase) flags += 'i';
  let regex = new RegExp(query, flags);
  for(let match of txt.matchAll(regex)) {
      matches.push({start: match.index, end: match.index + match[0].length});
  }

  // Highlight each match (reverse order so earlier offsets stay valid)
  for(let m of matches.reverse()) {
      let pos = 0;
      for(let i=0; i<texts.length; i++) {
          let len = texts[i].length;
          if(pos + len > m.start && pos < m.end) {
              let nStart = Math.max(0, m.start - pos);
              let nEnd = Math.min(len, m.end - pos);
              let mid = nodes[i].splitText(nStart);
              mid.splitText(nEnd - nStart);
              
              let mark = document.createElement('mark');
              mark.appendChild(mid.cloneNode(true));
              mid.replaceWith(mark);
          }
          pos += len;
      }
  }
}

function highlightAll(search, isRegex, useCase) {
  $('.msg-card').each((i, el) => { highLight(search, el, isRegex, useCase) });
}
