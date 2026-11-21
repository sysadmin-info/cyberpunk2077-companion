const UI_LANG = document.documentElement?.lang === "en" ? "en" : "pl";
const $ = (q) => document.querySelector(q);
const $$ = (q) => [...document.querySelectorAll(q)];
let state = null;
let lastScreenshotKey = null;
let requestBusy = false;
let selectionDirty = false;

const codeLabels = {
  pl: {core:'podstawowe', recommended:'zalecane', optional:'opcjonalne', info:'informacja', high:'wysoka', medium:'średnia', low:'niska', raw:'dane surowe', route:'ścieżka', unknown:'nieustalone', signal:'sygnał',
    normal:'zwykły',rewind:'cofnięcie',ending:'zakończenie','point-of-no-return':'punkt bez powrotu', Corporate:'Korporacja',Corpo:'Korporacja',Nomad:'Nomada',StreetKid:'Dziecko ulicy',Streetkid:'Dziecko ulicy',
    Easy:'Łatwy',Normal:'Normalny',Hard:'Trudny',VeryHard:'Bardzo trudny',post_quest:'po zadaniu', world_event:'wydarzenie świata', conditional_dialogue:'dialog warunkowy',npc_dialogue:'rozmowa z NPC',ambient_dialogue:'rozmowa w tle',hidden_interaction:'ukryta interakcja',timed_encounter:'wydarzenie czasowe'},
  en: {'point-of-no-return':'point of no return',Corporate:'Corpo',StreetKid:'Streetkid',VeryHard:'Very hard',post_quest:'after a quest',world_event:'world event',conditional_dialogue:'conditional dialogue',npc_dialogue:'NPC dialogue',ambient_dialogue:'background conversation',hidden_interaction:'hidden encounter',timed_encounter:'timed event'}
};
function displayCode(value) {return Object.hasOwn(codeLabels[UI_LANG],value) ? codeLabels[UI_LANG][value] : value;}
function renderSaveSelection(s) {
  const selection = s.save_selection;
  if (!selection) return;
  const picker = $('#save-select');
  const desired = selectionDirty ? picker.value : (selection.selected_save || '');
  const saves = selection.saves || [];
  picker.innerHTML = '<option value="">Latest automatically</option>' + saves.map(x =>
    `<option value="${esc((x.save_id || x.save_name))}">${esc(x.save_name)}${x.save_id && x.save_id !== x.save_name ? " ["+esc(x.save_id)+"]" : ""} · ${esc(x.timestamp)} · level ${esc(x.level)} · ${esc(x.playthrough_hours)} h</option>`).join('');
  if (desired && !saves.some(x => (x.save_id || x.save_name) === desired)) {
    picker.innerHTML += `<option value="${esc(desired)}">${esc(desired)} — unavailable</option>`;
  }
  picker.value = desired;
  $('#save-current').textContent = `Loaded: ${selection.active_save || 'none'} · ${selection.mode === 'manual' ? 'manual selection' : 'latest automatically'}`;
}


const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const metric = (label, value) => `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`;
const badge = (text, cls) => `<span class="badge ${esc(cls)}">${esc(text)}</span>`;
const money = (value) => value == null ? '—' : `€$${Number(value).toLocaleString(UI_LANG)}`;
const displayItem = (x) => x?.name || x?.id || x?.tweakdb_value || 'unrecognized';
const aliasMeta = (x) => x?.catalog_name && String(x.catalog_name).toLowerCase() !== String(x.name || '').toLowerCase() ? `<div class="item-alias">catalog: ${esc(x.catalog_name)} · source: ${esc(x.name_source || 'alias')}</div>` : '';

function kv(target, rows) {
  $(target).innerHTML = rows.map(([k,v]) => `<div class="k">${esc(k)}</div><div class="v">${v}</div>`).join('');
}

function render(s, skipUnchangedIconic = false) {
  state = s;
  syncFork(s);
  renderSaveSelection(s);
  const omitted = (s.scan_warnings || []).length ? 'Skipped saves: ' + s.scan_warnings.join(', ') : '';
  $('#scan-warning').textContent = [s.scan_stale ? 'Showing the last successful read of this slot. The current files are incomplete or unreadable. Refresh before exporting or changing a mark.' : '', omitted].filter(Boolean).join(' ');
  $('#legacy-import')?.classList.toggle('hidden', !s.ok || !s.hidden_encounters?.legacy_available);
  $('#loading').classList.add('hidden');
  if (!s.ok) {
    $('#error').classList.remove('hidden');
    $('#error').textContent = s.error || 'No data';
    $$('.tab-panel').forEach(panel => panel.classList.add('hidden'));
    return;
  }
  $('#error').classList.add('hidden');
  const activeTab = document.querySelector('.tabs button.active')?.dataset.tab || 'overview';
  $$('.tab-panel').forEach(panel => panel.classList.toggle('hidden', panel.id !== activeTab));

  const l = s.latest;
  $('#hero').innerHTML = `
    <div><div class="eyebrow">${esc(displayCode(l.life_path))} // ${esc(displayCode(l.difficulty))} // PATCH ${esc(l.patch)}</div><div class="big">LEVEL ${esc(l.level)}</div><div class="sub">${esc(l.save_name)} · ${esc(l.timestamp_string)}</div></div>
    <div class="right"><div class="eyebrow">PLAYTHROUGH</div><div class="big">${esc(l.playthrough_hours)} h</div><div class="sub">Street Cred ${esc(l.street_cred)} · ${l.has_phantom_liberty ? 'Phantom Liberty active' : 'Base game'}</div></div>`;

  $('#metrics').innerHTML = [
    ['Save', l.save_name], ['Play time', `${l.playthrough_hours} h`], ['Street Cred', l.street_cred],
    ['Eurodollars', money(l.wallet_eurodollars)], ['Finished IDs', l.finished_quests.length], ["Saves", s.stats.save_count],
    ['Equipped', (l.equipped_items || []).length], ['Parser', l.binary_parser_status === 'ok' ? 'sav.dat OK' : l.binary_parser_status]
  ].map(x => metric(...x)).join('');

  const labels = {body:'Body', intelligence:'Intelligence', reflexes:'Reflexes', technical_ability:'Tech', cool:'Cool'};
  $('#attributes').innerHTML = Object.entries(l.attributes).map(([k,v]) => `<div class="attribute"><div class="n">${esc(v)}</div><div class="k">${esc(labels[k]||k)}</div></div>`).join('');

  kv('#current', [
    ['Tracked quest', `<code>${esc(l.tracked_quest || '[none]')}</code>`],
    ['Tracked entry', `<code>${esc(l.tracked_quest_entry || '[nothing]')}</code>`],
    ['Lifepath', esc(displayCode(l.life_path))], ['Difficulty', esc(displayCode(l.difficulty))],
    ['Playthrough ID', `<code>${esc(l.playthrough_id)}</code>`],
    ['Point of no return', l.is_point_of_no_return ? 'YES' : 'no'],
    ['EndGameSave', l.is_end_game_save ? 'YES' : 'no'], ['Modded', l.is_modded ? 'YES' : 'no']
  ]);

  const screenshotKey = `${l.save_id || l.save_name}|${l.timestamp_iso}|${l.has_screenshot || ''}`;
  if (screenshotKey !== lastScreenshotKey) {
    const img = $('#screenshot');
    img.hidden = !l.has_screenshot;
    if (l.has_screenshot) img.src = `/api/screenshot?t=${Date.now()}`; else img.removeAttribute?.('src');
    lastScreenshotKey = screenshotKey;
  }

  $('#decisions').innerHTML = s.decisions.map(d => `
    <div class="decision ${d.active ? 'active':'inactive'}">
      <div class="group">${esc(d.group)}</div><div class="label">${esc(d.label)}</div>
      <div class="fact">${esc(d.fact)}=${esc(d.value)}</div>
      <div class="confidence">confidence: ${esc(displayCode(d.confidence))}</div>
    </div>`).join('') || '<div class="muted">No supported flags found in this save.</div>';

  renderCharacter(); renderLoadout(); renderReadiness(); renderHiddenEncounters(); renderInventory();
  if (!skipUnchangedIconic || renderedIconicSignature !== JSON.stringify(s.iconic_weapons || {})) renderIconic();
  renderQuickhacks(skipUnchangedIconic); renderChoices(skipUnchangedIconic);
  renderEndings(); renderQuests(); renderHistory();

  kv('#parser', [
    ['Status', `<code>${esc(l.binary_parser_status)}</code>`],
    ['Node count', esc(l.binary_node_count)],
    ['FactsTable entries', esc(l.binary_fact_entries)],
    ['Resolved binary facts', esc(Object.keys(l.resolved_binary_facts).length)],
    ['PlayerDevelopment', `<code>${esc(l.player_development_status || '—')}</code>`],
    ['EquipmentSystem', `<code>${esc(l.equipment_status || '—')}</code>`],
    ['StatPoolsSystem', `<code>${esc(l.stat_pools_status || '—')}</code>`],
    ['StatsSystem', `<code>${esc(l.player_stats_status || '—')}</code>`],
    ['Player itemData', `${esc(l.player_inventory_parsed_count)} / ${esc(l.player_inventory_declared_count)}`],
    ['All itemData', esc(l.all_item_record_count)],
    ['Item catalog', esc((l.item_catalog||{}).external_records || 0)],
    ['Game version', esc(l.game_version)], ['Save version', esc(l.save_version)]
  ]);
  $('#finished').textContent = l.finished_quests.join(' ');
}

function renderCharacter() {
  const l = state.latest;
  $('#development-metrics').innerHTML = [
    ['Attribute points', l.available_attribute_points ?? '—'], ['Perk points', l.available_perk_points ?? '—'],
    ['Relic points', l.available_relic_points ?? '—'], ['Purchased nodes', l.purchased_perk_count ?? 0],
    ['Total ranks', l.purchased_perk_ranks ?? 0], ['Parser', l.player_development_status || '—']
  ].map(x => metric(...x)).join('');

  const skills = l.skills || [];
  $('#skill-grid').innerHTML = skills.map(x => `<div class="skill-card">
    <div class="skill-name">${esc(x.name)}</div><div class="skill-level">${esc(x.level)}</div>
    <div class="skill-exp">XP at the current level: <strong>${esc(x.exp)}</strong></div><div class="fact">${esc(x.type)}</div>
  </div>`).join('') || '<div class="muted">PlayerDevelopmentData could not be read.</div>';

  const q = ($('#perk-filter')?.value || '').toLowerCase();
  const trees = (l.perk_trees || []).map(tree => ({...tree, perks:(tree.perks||[]).filter(p => JSON.stringify(p).toLowerCase().includes(q) || tree.name.toLowerCase().includes(q))})).filter(tree => tree.perks.length);
  $('#perk-trees').innerHTML = trees.map(tree => `<section class="perk-tree">
    <div class="perk-tree-head"><div><div class="eyebrow">${esc(tree.raw_type)}</div><h3>${esc(tree.name)}</h3></div><div class="muted">${esc(tree.purchased_count)} nodes / ${esc(tree.purchased_ranks)} ranks</div></div>
    <div class="perk-list">${tree.perks.map(p => `<div class="perk-row"><div><strong>${esc(p.name || p.id)}</strong>${p.inferred_id ? ' <span class="inferred">ID inferred</span>' : ''}<div class="fact">${esc(p.id)}</div></div><span class="badge active">RANK ${esc(p.rank)}</span></div>`).join('')}</div>
  </section>`).join('') || '<div class="muted">No matching purchased perks.</div>';

  const dp = l.development_points || [];
  $('#devpoints').innerHTML = `<table><thead><tr><th>Internal type</th><th>Meaning</th><th>Spent</th><th>Unspent</th></tr></thead><tbody>${dp.map(x => {
    const meaning = x.type === 'Attribute' ? 'Attribute points' : x.type === 'Primary' ? 'Perk points' : x.type === 'Espionage' ? 'Relic points' : 'internal / unknown';
    return `<tr><td><code>${esc(x.type)}</code></td><td>${esc(meaning)}</td><td>${esc(x.spent)}</td><td>${esc(x.unspent)}</td></tr>`;
  }).join('')}</tbody></table>`;
}

function renderLoadout() {
  const l = state.latest;
  const weapons = l.equipped_weapons || [];
  const cyberware = l.equipped_cyberware || [];
  const ps = l.player_stats || {};
  const health = ps.health || {};
  const savedPools = ps.saved_stat_pools || [];
  $('#loadout-metrics').innerHTML = [
    ['EquipmentSystem', l.equipment_status || '—'], ['Weapon slots', weapons.length], ['Cyberware slots', cyberware.length],
    ['Saved pools', ps.saved_stat_pool_count ?? savedPools.length], ['Max Health', health.max ?? '—'],
    ['Current Health', health.current_percent == null ? '—' : `${health.current_percent}%`], ['Saved Humanity', ps.saved_humanity_additive ?? '—']
  ].map(x => metric(...x)).join('');

  $('#equipped-weapons').innerHTML = weapons.map(x => `<div class="loadout-card weapon">
    <div class="loadout-slot">${esc(x.slot_label)}</div><div class="loadout-name">${esc(displayItem(x))}</div>${aliasMeta(x)}
    <div class="fact">${esc(x.id || x.tweakdb_value)}</div><div class="loadout-meta">hash ${esc(x.tweakdb_hash)} · seed ${esc(x.rng_seed ?? '—')}</div>
  </div>`).join('') || '<div class="muted">No active weapon slots could be read.</div>';

  $('#equipped-cyberware').innerHTML = cyberware.map(x => `<tr>
    <td><strong>${esc(x.slot_label)}</strong></td><td>${esc(displayItem(x))}${aliasMeta(x)}</td><td class="fact">${esc(x.id || x.tweakdb_value)}</td><td class="fact">${esc(x.tweakdb_hash)}</td>
  </tr>`).join('') || '<tr><td colspan="4" class="muted">No equipped cyberware could be read.</td></tr>';

  kv('#health-stats', [
    ['Parser', `<code>${esc(l.stat_pools_status || '—')}</code>`], ['Max Health', esc(health.max ?? '—')],
    ['Current', health.current_percent == null ? '—' : `${esc(health.current_percent)}%`],
    ['Source', `<code>${esc(health.source || '—')}</code>`], ['Resolution', `<code>${esc(health.status || 'unknown')}</code>`],
    ['Custom limit', esc(health.custom_limit ?? '—')], ['Change mode', `<code>${esc(health.change_mode || '—')}</code>`]
  ]);
  $('#health-resolution-note').innerHTML = esc(health.note || 'No further information about the source of Health.');

  const knownStats = ps.known_saved_stats || [];
  $('#stats-system-rows').innerHTML = knownStats.map(row => `<tr>
    <td><code>${esc(row.source || '—')}</code></td><td><strong>${esc(row.stat || '—')}</strong></td>
    <td>${esc(row.modifier_type_name || (row.modifier_type ?? '—'))}</td><td>${esc(row.value ?? '—')}</td>
    <td class="fact">${esc(row.stat_hash || '—')}</td>
  </tr>`).join('') || '<tr><td colspan="5" class="muted">No named StatsSystem inputs in this save.</td></tr>';

  $('#stat-pool-rows').innerHTML = savedPools.map(pool => `<tr${pool.is_health ? ' class="stat-pool-health"' : ''}>
    <td><strong>${esc(pool.type || '—')}</strong></td>
    <td><code>${esc(pool.stat || '—')}</code></td>
    <td>${esc(pool.max_value ?? '—')}</td>
    <td>${esc(pool.current_value ?? '—')}</td>
    <td>${esc(pool.custom_limit_value ?? '—')}</td>
    <td><code>${esc(pool.change_mode || '—')}</code></td>
    <td class="fact">${esc(pool.record_id || '—')}</td>
  </tr>`).join('') || '<tr><td colspan="7" class="muted">No StatPoolsSystem pools found for EntityID=1 in this save.</td></tr>';
  const cap = ps.cyberware_capacity || {};
  kv('#humanity-stats', [
    ['Parser', `<code>${esc(l.player_stats_status || '—')}</code>`],
    ['Record', `<code>${esc(ps.stats_system_record_name || ps.stats_system_record_id || '—')}</code>`],
    ['Saved Humanity additive', esc(ps.saved_humanity_additive ?? '—')],
    ['Constant modifiers', esc(ps.constant_modifier_count ?? 0)], ['Forced modifiers', esc(ps.forced_modifier_count ?? 0)],
    ['Effective Capacity', `<code>${esc(cap.status || 'not resolved')}</code>`]
  ]);
}

function renderReadiness() {
  const r = state.reaper_readiness || {};
  const overallCls = (r.overall_code || r.overall || '').toLowerCase().replace(/\s+/g, '-');
  $('#reaper-hero').innerHTML = `<div class="readiness-summary ${esc(overallCls)}"><div><div class="eyebrow">DON'T FEAR THE REAPER // ${esc(r.ruleset || '—')}</div><div class="readiness-status">${esc(r.overall || 'UNKNOWN')}</div><div class="readiness-headline">${esc(r.headline || '')}</div></div><div class="readiness-score"><span>${esc(r.core_ready ?? 0)}</span>/<strong>${esc(r.core_total ?? 0)}</strong><small>core build</small></div></div>`;

  $('#reaper-metrics').innerHTML = [
    ['Core', `${r.core_ready ?? 0}/${r.core_total ?? 0}`], ['Recommended checks passed', `${r.recommended_ready ?? 0}/${r.recommended_known ?? 0}`],
    ['Equipped cyberware', r.equipped_cyberware_count ?? 0], ['Weapon slots', r.equipped_weapon_count ?? 0]
  ].map(x => metric(...x)).join('');

  const profiles = (r.combat_readiness || {}).profiles || [];
  const route = r.route_eligibility || {};
  $('#reaper-profiles').innerHTML = profiles.map(x => `<div class="profile-card ${esc(x.status)}"><div class="eyebrow">COMBAT PROFILE</div><div class="profile-title">${esc(x.label)}</div>${badge(x.status === 'ready' ? 'READY' : 'PARTIAL', `readiness-${x.status}`)}<div class="muted">${esc(x.evidence)}</div></div>`).join('') +
    `<div class="profile-card route"><div class="eyebrow">ROUTE ELIGIBILITY</div><div class="profile-title">${esc(displayCode(route.status || 'unknown'))}</div>${badge(route.status === 'signal' ? 'SIGNAL' : 'UNCONFIRMED', `readiness-${route.status || 'unknown'}`)}<div class="muted">${esc(route.value || '')}<br>${esc(route.note || '')}</div></div>`;

  const labels = {ready:'READY', partial:'NEEDS WORK', missing:'MISSING', unknown:'UNCONFIRMED', optional:'OPTIONAL', info:'INFO', signal:'SIGNAL'};
  const order = ['core','recommended','optional','info'];
  const groups = {};
  (r.checks || []).forEach(x => (groups[x.group] ||= []).push(x));
  $('#reaper-groups').innerHTML = Object.entries(groups).map(([group, rows]) => `<section class="readiness-group"><div class="readiness-group-head"><h3>${esc(group)}</h3><span class="muted">${esc(rows.length)} checks</span></div><div class="readiness-list">${rows.sort((a,b) => order.indexOf(a.importance)-order.indexOf(b.importance)).map(x => `<div class="readiness-row ${esc(x.status)}"><div class="readiness-main"><div class="readiness-label">${esc(x.label)}</div><div class="readiness-why">${esc(x.why)}</div>${(x.evidence||[]).length ? `<div class="fact readiness-evidence">${(x.evidence||[]).map(esc).join('<br>')}</div>` : ''}${x.caveat ? `<div class="readiness-caveat">${esc(x.caveat)}</div>` : ''}</div><div class="readiness-side">${badge(labels[x.status] || x.status, `readiness-${x.status}`)}<div class="readiness-value">${esc(x.value)}</div><div class="readiness-importance">${esc(displayCode(x.importance))}</div></div></div>`).join('')}</div></section>`).join('');

  const actions = r.next_actions || [];
  $('#reaper-next').innerHTML = actions.length ? actions.map((x,i) => `<div class="next-action"><span>${i+1}</span><div><strong>${esc(x.label)}</strong><div class="muted">${esc(x.value)} · ${esc(x.why)}</div></div></div>`).join('') : '<div class="ok-text">All core checks passed under the current rules.</div>';
  $('#reaper-notes').innerHTML = (r.notes || []).map(x => `<li>${esc(x)}</li>`).join('');
}

const encounterTypeLabels = {
  npc_dialogue: 'NPC dialogue', ambient_dialogue: 'background conversation', hidden_interaction: 'hidden encounter',
  timed_encounter: 'timed event', post_quest: 'after a quest', world_event: 'world event',
  conditional_dialogue: 'conditional dialogue'
};
const encounterStatusLabels = {unknown:'unknown', discovered:'discovered', completed:'completed'};
const verificationLabels = {
  game_data:'game data', multi_source:'confirmed', community:'community', user_observation:'player observation',
  needs_verification:'awaiting verification', unverified:'unverified'
};

function fillSelect(selector, values, firstLabel) {
  const el = $(selector);
  if (!el) return;
  const current = el.value;
  el.innerHTML = `<option value="">${esc(firstLabel)}</option>` + values.map(v => `<option value="${esc(v)}">${esc(displayCode(v))}</option>`).join('');
  if ([...el.options].some(x => x.value === current)) el.value = current;
}

function encounterConditionSummary(x) {
  const c = x.conditions || {};
  const bits = [];
  if (c.do_not_attack_first) bits.push('do not start a fight');
  else if (c.peaceful_approach) bits.push('approach peacefully');
  if (c.wait_after_objective) bits.push('stay after completing the objective');
  if (c.time_of_day) bits.push(`time: ${c.time_of_day}`);
  if (c.choice_sensitive) bits.push('depends on your choice');
  return bits.join(' · ') || 'no additional condition';
}

function renderHiddenEncounters() {
  const payload = state.hidden_encounters || {};
  const records = payload.records || [];
  const filters = payload.filters || {};
  fillSelect('#enc-district', filters.districts || [], 'All districts');
  fillSelect('#enc-type', filters.interaction_types || [], 'All types');
  fillSelect('#enc-activity', filters.related_activities || [], 'All quests and activities');

  const q = ($('#enc-search')?.value || '').toLowerCase().trim();
  const district = $('#enc-district')?.value || '';
  const type = $('#enc-type')?.value || '';
  const activity = $('#enc-activity')?.value || '';
  const status = $('#enc-status')?.value || '';
  const risk = $('#enc-risk')?.value || '';
  const time = $('#enc-time')?.value || '';
  const peaceful = $('#enc-peaceful')?.value || '';
  const doNotShoot = Boolean($('#enc-do-not-shoot')?.checked);

  const visible = records.filter(x => {
    const c = x.conditions || {};
    const related = x.related_activity || {};
    if (q && !JSON.stringify(x).toLowerCase().includes(q)) return false;
    if (district && x.district !== district) return false;
    if (type && x.interaction_type !== type) return false;
    if (activity && related.name !== activity) return false;
    if (status && x.user_status !== status) return false;
    if (risk && x.miss_risk !== risk) return false;
    if (time === 'required' && !c.time_of_day) return false;
    if (time === 'none' && c.time_of_day) return false;
    if (peaceful === 'yes' && !c.peaceful_approach) return false;
    if (peaceful === 'no' && c.peaceful_approach) return false;
    if (doNotShoot && !c.do_not_attack_first) return false;
    return true;
  });

  const counts = payload.counts || {};
  $('#hidden-encounter-metrics').innerHTML = [
    ['In the list', counts.total ?? records.length], ['Unknown', counts.unknown ?? 0],
    ['Discovered', counts.discovered ?? 0], ['Completed', counts.completed ?? 0],
    ['Hold fire', counts.do_not_attack_first ?? 0]
  ].map(x => metric(...x)).join('');
  $('#hidden-encounter-count').textContent = `Showing ${visible.length} of ${records.length} entries.`;

  const riskLabel = {high:'easy to miss', medium:'medium risk', low:'low risk'};
  $('#hidden-encounter-list').innerHTML = visible.map(x => {
    const c = x.conditions || {};
    const rel = x.related_activity || {};
    const verification = x.verification || {};
    const sourceRows = (x.sources || []).map(src => {
      const link = src.url ? `<a href="${esc(src.url)}" target="_blank" rel="noopener noreferrer">${esc(src.title)}</a>` : `<span>${esc(src.title)}</span>`;
      return `<li><strong>${esc(src.kind)}</strong> · ${link}${src.supports ? `<div class="muted">${esc(src.supports)}</div>` : ''}</li>`;
    }).join('');
    return `<article class="encounter-card ${c.do_not_attack_first ? 'do-not-shoot' : ''}">
      <div class="encounter-card-top">
        <div>
          <div class="encounter-place">${esc(x.subdistrict || x.district)} <span>· ${esc(x.location)}</span></div>
          <h3>${esc(x.title)}</h3>
        </div>
        <div class="encounter-badges">${badge(encounterTypeLabels[x.interaction_type] || x.interaction_type, 'encounter-type')}${badge(riskLabel[x.miss_risk] || x.miss_risk, `encounter-risk-${x.miss_risk}`)}${c.do_not_attack_first ? badge('HOLD FIRE', 'encounter-no-shoot') : ''}</div>
      </div>
      <div class="encounter-hint">${esc(x.hint)}</div>
      <div class="encounter-condition"><strong>Condition:</strong> ${esc(encounterConditionSummary(x))}</div>
      <div class="encounter-footer">
        <div class="encounter-related">${rel.name ? `<span class="muted">Related:</span> ${esc(rel.name)}` : '<span class="muted">No related quest</span>'}</div>
        <label class="encounter-status-control">Status
          <select class="encounter-status-select" data-encounter-id="${esc(x.id)}">
            <option value="unknown" ${x.user_status === 'unknown' ? 'selected' : ''}>Unknown</option>
            <option value="discovered" ${x.user_status === 'discovered' ? 'selected' : ''}>Discovered</option>
            <option value="completed" ${x.user_status === 'completed' ? 'selected' : ''}>Completed</option>
          </select>
        </label>
      </div>
      <details class="encounter-details">
        <summary>Sources and verification details</summary>
        <div class="encounter-detail-grid">
          <div><div class="eyebrow">VERIFICATION</div>${badge(verificationLabels[verification.status] || verification.status || '—', `verification-${verification.status || 'unverified'}`)}<p>${esc(verification.note || '—')}</p><div class="muted">Patch: ${esc(verification.verified_patch || 'unknown')}</div></div>
          <div><div class="eyebrow">SOURCES</div><ul class="encounter-sources">${sourceRows}</ul></div>
        </div>
        ${c.notes ? `<div class="encounter-tech-note"><strong>Conditions:</strong> ${esc(c.notes)}</div>` : ''}
        ${x.editorial_notes ? `<div class="encounter-tech-note"><strong>Editor's note:</strong> ${esc(x.editorial_notes)}</div>` : ''}
        <div class="fact encounter-id">${esc(x.id)}</div>
      </details>
    </article>`;
  }).join('') || '<article class="panel"><div class="muted">No entries match these filters.</div></article>';
}

async function updateHiddenEncounterStatus(encounterId, status, selectEl) {
  selectEl.disabled = true;
  try {
    const r = await safePost('/api/hidden-encounters/status', {
      method: 'POST', cache: 'no-store', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({id: encounterId, status, scope:state.hidden_encounters.scope})
    });
    const out = await r.json();
    if (!r.ok || !out.ok) throw new Error(out.error || `HTTP ${r.status}`);
    const record = (state.hidden_encounters?.records || []).find(x => x.id === encounterId);
    if (record) record.user_status = status;
    const counts = state.hidden_encounters?.counts || {};
    if (counts) {
      counts.unknown = (state.hidden_encounters.records || []).filter(x => x.user_status === 'unknown').length;
      counts.discovered = (state.hidden_encounters.records || []).filter(x => x.user_status === 'discovered').length;
      counts.completed = (state.hidden_encounters.records || []).filter(x => x.user_status === 'completed').length;
    }
    renderHiddenEncounters();
  } catch (e) {
    alert(`Could not save the status: ${e}`);
    await load();
  } finally {
    selectEl.disabled = false;
  }
}

function renderInventory() {
  const l = state.latest;
  const rows = l.inventory_items || [];
  const knownFound = rows.filter(x => x.category !== 'currency' && x.category !== 'ending reward' && x.status !== 'absent');
  const probes = rows.filter(x => x.category === 'ending reward');
  const catalog = l.item_catalog || {};
  $('#inventory-metrics').innerHTML = [
    ['Wallet', money(l.wallet_eurodollars)], ['Storage ID', l.player_inventory_storage_id ?? '—'],
    ['Player itemData', `${l.player_inventory_parsed_count}/${l.player_inventory_declared_count}`], ['All itemData', l.all_item_record_count],
    ['Identified groups', catalog.resolved_item_groups ?? 0], ['Unknown groups', catalog.unknown_item_groups ?? 0], ['Local catalog entries', catalog.external_records ?? 0]
  ].map(x => metric(...x)).join('');
  const card = (x) => { const where = x.status === 'player' ? 'IN BACKPACK' : x.status === 'stash' ? 'STASH' : x.status === 'other' ? 'OTHER CONTAINER' : 'NOT FOUND'; const alias = x.resolved_via_catalog_alias ? `<div class="item-meta">catalog alias: ${esc((x.actual_ids||[]).join(', '))}</div>` : ''; return `<div class="item-card ${esc(x.status)}"><div class="item-top"><span class="item-category">${esc(x.category)}</span>${badge(where, `item-${x.status}`)}</div><div class="item-name">${esc(x.name)}</div><div class="fact">${esc(x.id)}</div><div class="item-meta">hash ${esc(x.tweakdb_hash)} · len ${esc(x.tweakdb_length)} · node ${esc((x.node_ids||[]).join(', ') || '—')}</div>${alias}</div>`; };
  $('#inventory-known').innerHTML = knownFound.map(card).join('') || '<div class="muted">No catalog items were identified.</div>';
  $('#reward-probes').innerHTML = probes.map(card).join('');
  const q = ($('#inventory-filter')?.value || '').toLowerCase();
  const all = (l.inventory_records || []).filter(x => JSON.stringify(x).toLowerCase().includes(q)); const shown = all.slice(0, 1200);
  $('#inventory-rows').innerHTML = shown.map(x => `<tr class="${x.resolved ? '' : 'unknown-item'}"><td>${badge(x.status === 'player' ? 'BACKPACK' : x.status === 'stash' ? 'STASH' : 'OTHER', x.status === 'player' ? 'item-player' : 'item-other')}</td><td>${x.resolved ? `<strong>${esc(x.name || x.id)}</strong>${aliasMeta(x)}` : '<span class="unknown-label">UNIDENTIFIED</span>'}</td><td class="fact">${esc(x.id || '—')}</td><td>${esc(x.category || x.subcategory || '—')}</td><td>${esc(x.quantity)}</td><td class="fact">${esc(x.tweakdb_hash)} / len ${esc(x.tweakdb_length)}</td><td class="fact">${esc((x.node_ids||[]).slice(0,8).join(', '))}${(x.node_ids||[]).length > 8 ? '…' : ''}</td></tr>`).join('');
  $('#catalog-note').innerHTML = catalog.present && catalog.external_records > 0 ? `<span class="ok-text">Catalog loaded:</span> ${esc(catalog.external_records)} NightCity Console records · ${esc(catalog.alias_overrides ?? 0)} name corrections for 2.31. Showing ${esc(shown.length)} of ${esc(all.length)} matching itemData groups.` : `<span class="warn-text">${catalog.verification === 'unverified' ? 'The optional catalog failed verification and was ignored.' : 'Full catalog not installed.'}</span> The panel shows raw hashes. To download the optional catalog, run <code>.\\update-item-catalog.ps1</code> or <code>.\\run.ps1 -UpdateCatalog</code>.`;
}

let iconicPage = 0;
const iconicPageSize = 20;
const iconicOpenDetails = new Set();
let renderedIconicSignature = null;
const acquisitionLabels = {loot:'Loot', quest:'Quest reward', crafting:'Crafting spec and crafting', exploration:'Exploration', purchase:'Purchase', account:'Account reward', unknown:'Unconfirmed'};
function guideLink(link) {
  if (!/^https:\/\/[^\s/]+\//i.test(link?.url || '')) return '';
  return `<a href="${esc(link.url)}" target="_blank" rel="noopener noreferrer">${esc(link.label)}</a>`;
}
function guideDetails(x) {
  const g = x.guide || {};
  const availabilityLabels = {decision_dependent:'Choice-dependent', account_or_promo:'Account reward', unknown:'Not assessed'};
  const checked = g.verification === 'source_checked';
  return `<div class="guide-status ${checked ? 'ok-text' : 'warn-text'}">${checked ? 'Source-checked guide' : 'Guide awaiting verification'}</div>
    <div class="muted">Guide requirements: ${esc(availabilityLabels[x.availability_class] || 'Not assessed')}</div>
    <div class="muted">${(x.collection_tags || []).map(t => esc({special_reward:'Special or promotional reward; other sources may exist',story_choice:'Depends on story choices'}[t] || t)).join(' · ')}</div>
    <div>${esc(acquisitionLabels[g.method] || 'Unconfirmed')}</div><p>${esc(x.acquisition)}</p>
    <details data-guide-id="${esc(x.id)}" ${iconicOpenDetails.has(x.id) ? 'open' : ''}><summary>Quest, NPC, conditions and sources</summary>
      ${g.quest ? `<p><strong>Quest:</strong> ${esc(g.quest)}</p>` : ''}
      ${g.npc ? `<p><strong>NPC:</strong> ${esc(g.npc)}</p>` : ''}
      ${g.conditions ? `<p><strong>Conditions / notes:</strong> ${esc(g.conditions)}</p>` : ''}
      <p class="muted">Availability in this save: not assessed.</p>
      <div class="guide-links">${(g.sources || []).map(guideLink).join('')}</div>
      ${g.checked_on ? `<p class="muted">Sources checked: ${esc(g.checked_on)}</p>` : ''}
    </details>`;
}
function renderIconic() {
  const payload = state.iconic_weapons || {};
  const records = payload.records || [];
  const counts = payload.counts || {};
  const q = ($('#iconic-search')?.value || '').toLowerCase().trim();
  const status = $('#iconic-status')?.value || '';
  const game = $('#iconic-game')?.value || '';
  const guideFilter = $('#iconic-guide-filter')?.value || '';
  const method = $('#iconic-method')?.value || '';
  const availability = $('#iconic-availability')?.value || '';
  const collection = $('#iconic-collection')?.value || '';
  const visible = records.filter(x => {
    if (q && !JSON.stringify(x).toLowerCase().includes(q)) return false;
    if (game && x.game !== game) return false;
    if (collection && !(x.collection_tags || []).includes(collection)) return false;
    const g = x.guide || {};
    if (guideFilter === 'map' && !(g.map_links || []).length) return false;
    if (guideFilter && guideFilter !== 'map' && (g.verification || 'needs_verification') !== guideFilter) return false;
    if (method && (g.method || 'unknown') !== method) return false;
    if (availability && (x.availability_class || 'unknown') !== availability) return false;
    if (status === 'owned' && !x.owned) return false;
    if (status && status !== 'owned' && x.status !== status) return false;
    return true;
  });
  $('#iconic-metrics').innerHTML = [
    ['In catalog', counts.total ?? records.length], ['Owned', counts.owned ?? 0], ['Missing from save', counts.missing ?? 0],
    ['Equipped', counts.equipped ?? 0], ['Backpack', counts.inventory ?? 0], ['Stash', counts.stash ?? 0], ['Other container', counts.other ?? 0], ['Unknown', counts.unknown ?? 0]
  ].map(x => metric(...x)).join('');
  const pages = Math.max(1, Math.ceil(visible.length / iconicPageSize));
  iconicPage = Math.max(0, Math.min(iconicPage, pages - 1));
  const shown = visible.slice(iconicPage * iconicPageSize, (iconicPage + 1) * iconicPageSize);
  $('#iconic-count').textContent = `Matches: ${visible.length} of ${records.length} models. On this page: ${shown.length}.`;
  $('#iconic-page').textContent = `Page ${iconicPage + 1} of ${pages}`;
  $('#iconic-prev').disabled = iconicPage === 0;
  $('#iconic-next').disabled = iconicPage >= pages - 1;
  $('#iconic-page-bottom').textContent = $('#iconic-page').textContent;
  $('#iconic-prev-bottom').disabled = iconicPage === 0;
  $('#iconic-next-bottom').disabled = iconicPage >= pages - 1;
  const gc = payload.guide_counts || {};
  $('#iconic-guide-summary').textContent = `Full catalog: ${gc.source_checked ?? 0} source-checked guides · ${gc.needs_verification ?? 0} pending verification · ${gc.with_map ?? 0} models with a map marker link.`;
  const labels = {equipped:'EQUIPPED', inventory:'BACKPACK', stash:'STASH', unknown:'UNKNOWN', other:'OTHER CONTAINER', missing:'MISSING'};
  const games = {base:'BASE GAME', phantom_liberty:'PHANTOM LIBERTY'};
  $('#iconic-rows').innerHTML = shown.map(x => `<tr class="iconic-${esc(x.status)}">
    <td>${badge(labels[x.status] || x.status, `iconic-status ${x.status}`)}<div class="muted">${(x.locations || []).filter(y => y !== x.status).map(y => esc(labels[y])).join(' · ')}</div></td>
    <td><strong>${esc(x.name)}${UI_LANG === "pl" && x.name_pl ? ' / ' + esc(x.name_pl) : ''}</strong><details><summary>Technical identifiers</summary><div class="fact">${esc((x.tweakdb_ids || []).join(' · '))}</div></details></td>
    <td>${esc(games[x.game] || x.game)}<div class="muted">${esc(x.weapon_type)}</div></td>
    <td>${guideDetails(x)}</td>
    <td>${esc(x.location)}${x.guide?.fast_travel ? `<p><strong>Fast travel:</strong> ${esc(x.guide.fast_travel)}</p>` : ''}<div class="guide-links">${(x.guide?.map_links || []).map(guideLink).join('') || '<span class="muted">No confirmed link to a map marker.</span>'}</div></td>
  </tr>`).join('') || '<tr><td colspan="5" class="muted">No results for these filters.</td></tr>';
  renderedIconicSignature = JSON.stringify(payload);
}

let renderedQuickhackSignature = null;
let renderedChoiceSignature = null;
let discoverySaveKey = null;
const choiceOpenDetails = new Set();
const quickhackOpenDetails = new Set();
const tierLabel = x => x == null ? 'unknown tier' : ['','I','II','III','IV','V'][x] || String(x);
const choiceStatusLabels = {done:'COMPLETION CONFIRMED', active:'TRACKED QUEST', signal:'SAVE SIGNAL', unknown:'UNKNOWN'};

function resetDiscoveryForSave() {
  const l = state.latest;
  const key = `${l.playthrough_id || ''}|${l.save_id || l.save_name || ''}`;
  if (key !== discoverySaveKey) {
    choiceOpenDetails.clear(); quickhackOpenDetails.clear();
    renderedChoiceSignature = null; renderedQuickhackSignature = null;
    discoverySaveKey = key;
  }
}

function quickhackRows() {
  const q = ($('#quickhack-search').value || '').toLocaleLowerCase(UI_LANG);
  const kind = $('#quickhack-kind').value, location = $('#quickhack-location').value, tier = $('#quickhack-tier').value;
  return (state.quickhacks?.records || []).filter(x => {
    const text = [x.name, x.name_pl, x.id, x.family].join(' ').toLocaleLowerCase(UI_LANG);
    return text.includes(q) && (!kind || x.kind === kind)
      && (!location || (location === 'owned' ? x.owned : location === 'other' ? !x.owned : x.location === location))
      && (!tier || (tier === 'unknown' ? x.tier == null : String(x.tier) === tier));
  });
}

function renderQuickhacks(skipUnchanged = false) {
  resetDiscoveryForSave();
  const p = state.quickhacks || {}, counts = p.counts || {};
  const signature = JSON.stringify([p, ...['#quickhack-search','#quickhack-kind','#quickhack-location','#quickhack-tier'].map(x => $(x).value)]);
  if (skipUnchanged && signature === renderedQuickhackSignature) return;
  $('#quickhack-metrics').innerHTML = [['Program variants',counts.owned_program_variants ?? 0],['Crafting spec variants',counts.owned_recipe_variants ?? 0],['Families',counts.families ?? 0]].map(x => metric(...x)).join('');
  $('#quickhack-deck').innerHTML = (p.operating_systems || []).map(x => `<div class="loadout-card weapon"><div class="loadout-slot">${esc(x.slot_label)}</div><div class="loadout-name">${esc(displayItem(x))}</div><div class="fact">${esc(x.id || x.tweakdb_value)}</div></div>`).join('') || '<p class="muted">No equipped operating system was identified.</p>';
  $('#quickhack-slot-note').textContent = p.installed_quickhacks?.note || 'Installed quickhacks could not be read.';
  const rows = quickhackRows();
  const families = [...new Set(rows.map(x => x.family))];
  $('#quickhack-count').textContent = `${rows.length} records · ${families.length} families. ${p.ownership_scan_complete ? '' : 'Container data is incomplete. Results may be partial.'} Unidentified inventory items: ${counts.unclassified_inventory_records ?? 0}.`;
  const loc = {player:'BACKPACK',stash:'STASH',other:'OTHER CONTAINER',unknown:'UNCONFIRMED CONTAINER'};
  $('#quickhack-list').innerHTML = families.map(family => {
    const items = rows.filter(x => x.family === family), first = items[0];
    return `<article class="panel discovery-card"><div class="eyebrow">QUICKHACK</div><h3>${esc((UI_LANG === "pl" && first.name_pl) || first.name)}</h3>${UI_LANG === "pl" && first.name_pl ? `<p class="muted">${esc(first.name)}</p>` : ''}
      <div class="quickhack-variants">${items.map(x => `<div class="quickhack-variant"><div><strong>${x.kind === 'recipe' ? 'Crafting spec' : 'Program'} · ${esc(tierLabel(x.tier))}${x.iconic ? ' · iconic' : ''}</strong><div class="muted">${esc(loc[x.location] || x.location)} · qty ${esc(x.quantity)}${!x.owned ? ' · ownership unconfirmed' : ''}</div></div>${badge(x.kind === 'recipe' ? 'CRAFTING SPEC' : 'PROGRAM',x.kind === 'recipe' ? 'signal' : 'done')}</div>`).join('')}</div>
      <details class="technical-details" data-quickhack-id="${esc(family)}" ${quickhackOpenDetails.has(family) ? 'open' : ''}><summary>Identifiers and evidence</summary>${items.map(x => `<p><code>${esc(x.id || x.tweakdb_value)}</code><br><span class="muted">${esc(x.identification)} · storage ${esc((x.storage_ids || []).join(', '))}</span></p>`).join('')}</details></article>`;
  }).join('') || '<article class="panel muted">No quickhacks match these filters. This does not establish what is installed in the cyberdeck slots.</article>';
  $('#quickhack-notes').innerHTML = (p.notes || []).map(x => `<li>${esc(x)}</li>`).join('');
  $('#quickhack-sources').innerHTML = (p.sources || []).map(guideLink).join('');
  renderedQuickhackSignature = signature;
}

// The finder runs only on request. Discard responses if the active save changes mid-scan.
let forkKey = '', forkSerial = 0, forkData = null, forkLimit = 20;
function syncFork(s) {
  const l = s.latest || {};
  const key = s.ok && !s.scan_stale ? JSON.stringify([l.playthrough_id,l.save_id,l.timestamp_iso]) : '';
  if (key === forkKey) return;
  forkKey = key; forkSerial++; forkData = null; forkLimit = 20;
  $('#fork-results').classList.add('hidden');
  $('#fork-status').textContent = '';
  $('#fork-summary').innerHTML = ''; $('#fork-rows').innerHTML = '';
  $('#fork-kind').value = 'all'; $('#fork-name').value = ''; $('#fork-stage').value = '';
  $('#fork-search').disabled = !key;
}
const forkStages = {candidate:'Quest active — candidate',songbird:'Songbird route',reed:'Reed route',
  past:'Quest complete, route unknown',signal:'Quest signal, route unknown',conflict:'Conflicting signals'};
function drawFork() {
  if (!forkData) return;
  const d = forkData, kind = $('#fork-kind').value || 'all', w = d.windows[kind];
  const index = new Map(d.rows.map(x => [x.slot,x]));
  function group(title, ids, empty) {
    return '<div class="decision"><h3>'+esc(title)+'</h3>'+(ids.length ? '<ul>'+ids.map(id=>{
      const r=index.get(id);
      return '<li><strong>'+esc(id)+'</strong> · '+esc(r.time)+' · '+(r.hours==null ? '—' : esc(r.hours)+' h')+' · '+esc(forkStages[r.stage])+'</li>';
    }).join('')+'</ul>' : '<p>'+esc(empty)+'</p>')+'</div>';
  }
  $('#fork-summary').innerHTML = group('Latest candidate to load',w.candidates,'No dated slot with evidence that the quest is active.')
    + group(w.candidates.length ? 'First later save with an identified route' : 'Earliest save with an identified route',w.first_confirmed,'No matching dated route evidence found.')
    + (w.both_routes ? '<p>Both routes appear in this history. Timestamps order the saves but do not prove they belong to the same branch.</p>' : '')
    + (w.same_time || w.candidates.length>1 || w.first_confirmed.length>1 ? '<p>Some slots share a timestamp. Their order cannot be established.</p>' : '');
  const q = $('#fork-name').value.trim().toLowerCase(), stage = $('#fork-stage').value;
  const rows = d.rows.filter(r => (kind === 'all' || r.kind===kind) && r.slot.toLowerCase().includes(q)
    && (!stage || stage === r.stage || (stage==='known' && ['songbird','reed'].includes(r.stage))));
  $('#fork-count').textContent = rows.length ? 'Showing saves: '+Math.min(forkLimit,rows.length)+' / '+rows.length : 'No matching saves.';
  $('#fork-rows').innerHTML = rows.slice(0,forkLimit).map(r => '<tr><td>'+esc(r.slot)+'</td><td>'+esc(r.time || '—')+'</td><td>'+(r.hours==null ? '—' : esc(r.hours)+' h')+'</td><td>'+esc(forkStages[r.stage])+'</td><td><code>'+esc(r.evidence.join(' · '))+'</code></td></tr>').join('');
  $('#fork-more').classList.toggle('hidden',forkLimit>=rows.length);
}
async function searchFork() {
  if (!forkKey) return;
  const serial=++forkSerial;
  $('#fork-search').disabled=true; $('#fork-results').classList.add('hidden');
  $('#fork-status').textContent='Reading local metadata…'; forkData=null; forkLimit=20;
  try {
    const resp=await fetch('/api/decision-saves/firestarter',{cache:'no-store'});
    const data=await resp.json();
    if (serial!==forkSerial) return;
    if (!resp.ok || !data.ok || data.selected_slot!==state.latest.save_id || data.selected_profile!==state.latest.playthrough_id) throw Error();
    if (data.reason==='no-profile') { $('#fork-status').textContent='The selected save has no playthrough ID. Select another save from the same character.'; return; }
    forkData=data;
    $('#fork-status').textContent='Slots in this playthrough: '+data.profile_slots+'.'
      +(data.unreadable ? ' Unreadable metadata skipped in this directory: '+data.unreadable+'.' : '')
      +(data.incomplete ? ' Related slots skipped for a missing or empty game file: '+data.incomplete+'.' : '');
    drawFork(); $('#fork-results').classList.remove('hidden');
  } catch {
    if (serial===forkSerial) $('#fork-status').textContent='Could not read the save history. Refresh the panel and search again.';
  } finally {
    if (serial===forkSerial) $('#fork-search').disabled=false;
  }
}
$('#fork-search').addEventListener('click',searchFork);
['#fork-kind','#fork-name','#fork-stage'].forEach(id=>$(id).addEventListener(id==='#fork-name'?'input':'change',()=>{forkLimit=20;drawFork();}));
$('#fork-more').addEventListener('click',()=>{forkLimit+=20;drawFork();});

function choiceRows() {
  const q = ($('#choice-search').value || '').toLocaleLowerCase(UI_LANG);
  const game = $('#choice-game').value, tag = $('#choice-tag').value, status = $('#choice-status').value;
  return (state.quest_choices?.records || []).filter(x => [x.title,x.hint,...(x.tags || []),...(x.search_aliases || [])].join(' ').toLocaleLowerCase(UI_LANG).includes(q)
    && (!game || x.game === game) && (!tag || (x.tags || []).includes(tag)) && (!status || x.save_evidence?.status === status));
}

function renderChoices(skipUnchanged = false) {
  resetDiscoveryForSave();
  const p = state.quest_choices || {}, counts = p.counts || {};
  const signature = JSON.stringify([p,...['#choice-search','#choice-game','#choice-tag','#choice-status'].map(x => $(x).value)]);
  if (skipUnchanged && signature === renderedChoiceSignature) return;
  const currentTag = $('#choice-tag').value;
  const tags = [...new Set((p.records || []).flatMap(x => x.tags || []))].sort((a,b) => a.localeCompare(b,UI_LANG));
  $('#choice-tag').innerHTML = '<option value="">All topics</option>' + tags.map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join('');
  $('#choice-tag').value = tags.includes(currentTag) ? currentTag : '';
  $('#choice-metrics').innerHTML = [['Quests covered',counts.total ?? 0],['Signals / tracked',(counts.signal || 0)+(counts.active || 0)],['Lifepath',p.lifepath || '—']].map(x => metric(...x)).join('');
  const rows = choiceRows();
  $('#choice-count').textContent = `${rows.length} of ${counts.total ?? 0} quests · guide last updated ${p.checked_on || '—'}. Quest progress and evidence of a chosen route are shown separately.`;
  $('#choice-list').innerHTML = rows.map(x => {
    const evidence = x.save_evidence || {status:'unknown',evidence:[]};
    return `<article class="panel discovery-card"><div class="eyebrow">${x.game === 'phantom_liberty' ? 'PHANTOM LIBERTY' : 'BASE GAME'}</div><h3>${esc(x.title)}</h3>
      <div class="choice-state">${badge(choiceStatusLabels[evidence.status] || 'UNKNOWN', evidence.status)}</div>
      <p class="discovery-hint">${esc(x.hint)}</p><div class="choice-tags">${(x.tags || []).map(t => `<span>${esc(t)}</span>`).join('')}</div>
      <details class="choice-spoilers" data-choice-id="${esc(x.id)}" ${choiceOpenDetails.has(x.id) ? 'open' : ''}><summary>Show consequences · spoilers</summary>
        ${evidence.label ? '<p><strong>Route in the selected save:</strong> '+esc(evidence.label)+'</p>' : ''}
        <p><strong>Decision point:</strong> ${esc(x.decision_point)}</p>
        ${(x.branches || []).map(b => `<section class="choice-branch"><h4>${esc(b.label)}</h4>${b.condition ? `<p class="branch-condition"><strong>Condition:</strong> ${esc(b.condition)}</p>` : ''}<p><strong>What to do:</strong> ${esc(b.action)}</p><p><strong>Immediate:</strong> ${esc(b.immediate)}</p>${b.delayed ? `<p class="branch-delayed"><strong>Later:</strong> ${esc(b.delayed)}</p>` : ''}${b.reward ? `<p><strong>Reward:</strong> ${esc(b.reward)}</p>` : ''}</section>`).join('')}
        ${(x.notes || []).length ? `<ul>${x.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
        <div class="guide-links">${(x.sources || []).map(guideLink).join('')}</div>
      </details>
      <details class="technical-details"><summary>Save evidence</summary><p class="fact">${esc((evidence.evidence || []).join(' · ') || 'No supported evidence.')}</p><p class="muted">Quest state does not confirm the outcome of a choice.</p></details>
    </article>`;
  }).join('') || '<article class="panel muted">No quests match these filters.</article>';
  $('#choice-notes').innerHTML = (p.notes || []).map(x => `<li>${esc(x)}</li>`).join('');
  renderedChoiceSignature = signature;
}

function renderEndings() {
  const rows = state.endings || [];
  $('#ending-cards').innerHTML = rows.map(x => `<div class="decision active ending-card"><div class="group">${esc(displayCode(x.kind))} // ${esc(x.marker)}</div><div class="label">${esc(x.ending)} — ${esc(x.name)}</div><div class="ending-count">${esc(x.save_count)} saves with this marker</div><div class="confidence">first: ${esc(x.first_seen)}<br>last: ${esc(x.last_seen)}</div><div class="fact ending-evidence">${(x.sample_saves||[]).map(y => `${esc(y.save)} → ${esc(y.tracked)}`).join('<br>')}</div></div>`).join('') || '<div class="muted">No supported ending markers found in the scanned history.</div>';
}
function renderQuests() { const q = ($('#quest-filter').value || '').toLowerCase(); const rows = state.quests.filter(x => JSON.stringify(x).toLowerCase().includes(q)); const labels={done:'completed',active:'active',started:'started',signal:'signal found',unknown:'no signal'}; $('#quest-rows').innerHTML=rows.map(x=>`<tr><td>${badge(labels[x.status]||x.status,x.status)}</td><td><code>${esc(x.id)}</code></td><td>${esc(x.name)}</td><td>${esc(x.group)}</td><td class="fact">${esc(x.evidence.join(', ') || '—')}</td></tr>`).join(''); }
function renderHistory() { const q=($('#history-filter').value||'').toLowerCase(); const rows=state.history.filter(x=>JSON.stringify(x).toLowerCase().includes(q)); $('#history-stats').innerHTML=[['Save count',state.stats.save_count],['Rewinds',state.stats.rewinds_detected],['EndGameSave',state.stats.endgame_saves],['Point of no return',state.stats.point_of_no_return_saves]].map(x=>metric(...x)).join(''); $('#history-rows').innerHTML=rows.map(x=>`<tr><td>${badge(displayCode(x.branch.kind),x.branch.kind)}</td><td>${esc(x.save_name)}</td><td>${esc(x.timestamp)}</td><td>${esc(x.playthrough_hours)}</td><td>${esc(x.level)}</td><td>${esc(x.street_cred)}</td><td>${esc(x.finished_count)}</td><td class="fact">${esc(x.tracked || '[nothing]')}</td></tr>`).join(''); }

async function load(selectionChange = false) {
  if (requestBusy) return;
  requestBusy = true;
  $('#refresh').disabled = true;
  $('#load-save').disabled = true;
  $('#save-select').disabled = true;
  try {
    if (selectionChange === true) {
      $('#save-error').textContent = '';
      const response = await safePost('/api/save-selection', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({save_name: $('#save-select').value || null})
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Could not select the save');
      selectionDirty = false;
    }
    const r = await fetch('/api/state?lang='+UI_LANG, {cache:'no-store'});
    const s = await r.json();
    if (!r.ok) throw new Error(s.error || 'Could not read the save');
    render(s, true);
  }
  catch (e) {
    $('#loading').classList.add('hidden');
    $('#save-error').textContent = String(e);
  }
  finally {
    requestBusy = false;
    $('#refresh').disabled = false;
    $('#load-save').disabled = false;
    $('#save-select').disabled = false;
  }
}

$('#save-select').addEventListener('change', () => { selectionDirty = true; });
$('#load-save').addEventListener('click', () => load(true));
$$('.tabs button').forEach(btn => btn.addEventListener('click', () => { if (state && !state.ok) return; $$('.tabs button').forEach(x => x.classList.toggle('active', x === btn)); $$('.tab-panel').forEach(x => x.classList.add('hidden')); $('#' + btn.dataset.tab).classList.remove('hidden'); }));
$('#refresh').addEventListener('click', load);
$('#quest-filter').addEventListener('input', () => state && renderQuests());
$('#perk-filter').addEventListener('input', () => state && renderCharacter());
$('#inventory-filter').addEventListener('input', () => state && renderInventory());
['#iconic-search','#iconic-status','#iconic-game','#iconic-guide-filter','#iconic-method','#iconic-collection','#iconic-availability'].forEach(sel => {
  const el = $(sel); if (el) el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => { iconicPage = 0; if (state) renderIconic(); });
});
function changeIconicPage(delta) {
  if (!state) return;
  iconicPage += delta;
  renderIconic();
  $('#iconic-count').scrollIntoView({block:'start'});
}
['#iconic-prev', '#iconic-prev-bottom'].forEach(sel => $(sel).addEventListener('click', () => changeIconicPage(-1)));
['#iconic-next', '#iconic-next-bottom'].forEach(sel => $(sel).addEventListener('click', () => changeIconicPage(1)));
$('#iconic-rows').addEventListener('toggle', e => {
  const id = e.target.dataset.guideId;
  if (id) e.target.open ? iconicOpenDetails.add(id) : iconicOpenDetails.delete(id);
}, true);
$('#history-filter').addEventListener('input', () => state && renderHistory());
['#quickhack-search','#quickhack-kind','#quickhack-location','#quickhack-tier'].forEach(sel => $(sel).addEventListener(sel.endsWith('search') ? 'input' : 'change', () => state && renderQuickhacks()));
['#choice-search','#choice-game','#choice-tag','#choice-status'].forEach(sel => $(sel).addEventListener(sel.endsWith('search') ? 'input' : 'change', () => state && renderChoices()));
$('#choice-list').addEventListener('toggle', e => {
  const id = e.target.dataset?.choiceId;
  if (id) e.target.open ? choiceOpenDetails.add(id) : choiceOpenDetails.delete(id);
}, true);
$('#quickhack-list').addEventListener('toggle', e => {
  const id = e.target.dataset?.quickhackId;
  if (id) e.target.open ? quickhackOpenDetails.add(id) : quickhackOpenDetails.delete(id);
}, true);
['#enc-search','#enc-district','#enc-type','#enc-activity','#enc-status','#enc-risk','#enc-time','#enc-peaceful','#enc-do-not-shoot'].forEach(sel => {
  const el = $(sel); if (el) el.addEventListener(el.tagName === 'INPUT' && el.type === 'search' ? 'input' : 'change', () => state && renderHiddenEncounters());
});
$('#hidden-encounter-list').addEventListener('change', e => {
  const el = e.target.closest('.encounter-status-select');
  if (el) updateHiddenEncounterStatus(el.dataset.encounterId, el.value, el);
});
let sessionToken;
async function safePost(url, init) {
  if (!sessionToken) {
    const s = await fetch('/api/session', {cache:'no-store'});
    if (!s.ok) throw new Error('Could not open a local session.');
    sessionToken = (await s.json()).token;
  }
  const r = await fetch(url, {...init, headers:{...init.headers,'X-Companion-Token':sessionToken}});
  if (r.status === 403) sessionToken = null;
  return r;
}
$('#legacy-import')?.addEventListener('click',async () => {
  try {
    const r = await safePost('/api/hidden-encounters/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:state.hidden_encounters.scope})});
    if (!r.ok) throw new Error('Import failed.');
    await load();
  } catch (e) { $('#save-error').textContent=String(e); }
});
$('#language')?.addEventListener('change', e => {
  const tab = document.querySelector('.tabs button.active')?.dataset.tab || 'overview';
  location.assign('/?lang='+(e.target.value==='en'?'en':'pl')+'#'+encodeURIComponent(tab));
});
if (typeof location !== 'undefined' && location.hash) {
  const tab = $$('.tabs button').find(el=>el.dataset.tab === location.hash.slice(1));
  tab?.click();
}
load(); setInterval(load, 15000);
