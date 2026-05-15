/**
 * Asset Browser shortcut icons — injected into accordion headers
 * and dropdown labels.
 *
 * Loaded via <head> injection in ui_gradio_extensions.py.
 * Reads AB_BASE from <meta name="ab-base-url">.
 *
 * Gradio 3.41.2 DOM reference:
 *   Accordion headers: .label-wrap  (first <span> = label, <span class="icon"> = arrow)
 *   Dropdown labels:   label > span (inside .gr-block)
 */
(function () {
  'use strict';

  var meta = document.querySelector('meta[name="ab-base-url"]');
  var AB_BASE = meta ? meta.content : '';
  if (!AB_BASE) return;

  var NS = 'http://www.w3.org/2000/svg';

  function createIcon() {
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', '14');
    svg.setAttribute('height', '14');
    svg.setAttribute('viewBox', '0 0 24 24');    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');

    var rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', '3'); rect.setAttribute('y', '3');
    rect.setAttribute('width', '18'); rect.setAttribute('height', '18');
    rect.setAttribute('rx', '2');
    svg.appendChild(rect);

    var circle = document.createElementNS(NS, 'circle');
    circle.setAttribute('cx', '8.5'); circle.setAttribute('cy', '8.5');
    circle.setAttribute('r', '1.5');
    svg.appendChild(circle);

    var path = document.createElementNS(NS, 'path');
    path.setAttribute('d', 'm21 15-5-5L5 21');
    svg.appendChild(path);

    return svg;
  }
  // type: 'accordion' -> icon right-aligned in .label-wrap (before arrow)
  // type: 'label'     -> icon after the <span> inside <label>
  var entries = [
    { id: 'base-model', match: 'Base Model',        hash: 'checkpoints', tooltip: 'Browse checkpoints in Asset Browser', type: 'label' },
    { id: 'refiner',    match: 'Refiner',           hash: 'checkpoints', tooltip: 'Browse checkpoints in Asset Browser', type: 'label' },
    { id: 'lora',       match: 'LoRA',              hash: 'loras',       tooltip: 'Browse LoRAs in Asset Browser',       type: 'accordion' },
    { id: 'embedding',  match: 'Textual Inversion', hash: 'embeddings',  tooltip: 'Browse Embeddings in Asset Browser',  type: 'accordion' },
  ];

  function makeLink(entry) {
    var a = document.createElement('a');
    a.href = AB_BASE + '#' + entry.hash;
    a.target = '_blank';
    a.title = entry.tooltip;
    a.style.cssText =
      'display:inline-flex;align-items:center;color:#bb86fc;text-decoration:none;' +
      'vertical-align:middle;opacity:0.7;transition:opacity .2s;cursor:pointer;';
    a.setAttribute('data-ab-link', entry.id);
    a.appendChild(createIcon());
    a.addEventListener('click', function (ev) {
      ev.stopPropagation();
      ev.preventDefault();
      window.open(a.href, '_blank');
    });
    a.addEventListener('mouseenter', function () { a.style.opacity = '1'; });
    a.addEventListener('mouseleave', function () { a.style.opacity = '0.7'; });
    return a;
  }
  function inject() {
    entries.forEach(function (e) {
      var tag = e.id;
      if (document.querySelector('a[data-ab-link="' + tag + '"]')) return;

      if (e.type === 'accordion') {
        var wraps = document.querySelectorAll('.label-wrap');
        for (var j = 0; j < wraps.length; j++) {
          var wrap = wraps[j];
          var textSpan = wrap.querySelector('span:first-child');
          if (!textSpan || textSpan.textContent.trim().indexOf(e.match) === -1) continue;

          // Make label-wrap a flex container so margin-left:auto pushes icon right
          wrap.style.display = 'flex';
          wrap.style.alignItems = 'center';

          var link = makeLink(e);
          link.style.marginLeft = 'auto';
          link.style.marginRight = '8px';

          // Insert before the arrow icon
          var arrow = wrap.querySelector('span.icon');
          if (arrow) {
            wrap.insertBefore(link, arrow);
          } else {
            wrap.appendChild(link);
          }
          break;
        }
      } else if (e.type === 'label') {
        var labels = document.querySelectorAll('label span');
        for (var k = 0; k < labels.length; k++) {
          if (labels[k].textContent.trim().indexOf(e.match) !== -1) {
            var link2 = makeLink(e);
            link2.style.marginLeft = '4px';
            labels[k].appendChild(link2);
            break;
          }
        }
      }
    });
  }

  // Gradio 3.41 renders progressively — retry until everything is found
  var delays = [300, 1000, 2500, 5000, 10000];
  function schedule() {
    delays.forEach(function (ms) { setTimeout(inject, ms); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedule);
  } else {
    schedule();
  }
})();
