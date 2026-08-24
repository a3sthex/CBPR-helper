/* GM Combat Reference — separate page for GMs (23.2) */
async function viewGmRef(view) {
  const genDv = [['Simple',9],['Everyday',13],['Difficult',15],['Professional',17],['Heroic',21],['Incredible',24],['Legendary',29]];
  const actions = [
    [T('Your Turn','Твой ход'), T('1 Move Action + 1 Action. Initiative = REF + 1d10.','1 Move Action + 1 Action. Инициатива = REF + 1d10.')],
    [T('Aimed Shot','Прицельный выстрел'), T('Trade Action for head ×3 / limb ×1 damage.','Потрать Action: голова ×3, конечность ×1 урона.')],
    [T('Cover','Укрытие'), T('Melee attackers −2/−4; ranged must beat SP.','Атакующие ближнего боя −2/−4; стрелки пробивают SP.')],
    [T('Suppressive Fire','Огонь на подавление'), T('Action + 10 rounds. WILL+Conc+1d10 vs REF+Autofire+1d10 in 25m.','Action + 10 пуль. WILL+Conc+1d10 vs REF+Autofire+1d10 в 25 м.')],
    [T('Autofire','Автоогонь'), T('Action + 10 rounds. Damage = 2d6 × (check − DV), capped by multiplier.','Action + 10 пуль. Урон = 2d6 × (бросок − DV), ограничен множителем.')],
    [T('Dual Wield','Два оружия'), T('Off-hand attack at −3 on same Action.','Атака второй рукой −3 на то же Action.')],
    [T('Death Save','Спасбросок смерти'), T('HP < 1: 1d10 ≤ BODY − penalty. 10 = fail.','HP < 1: 1d10 ≤ BODY − штраф. 10 = провал.')],
  ];
  view.innerHTML = `
  <div class="page-head"><div><h1>⚔️ ${T('GM Combat Reference','Боевой справочник GM')}</h1><div class="sub">${T('Quick tables and rules for running FNFF.','Быстрые таблицы и правила для FNFF.')}</div></div><a class="btn-sm" href="#/quick-reference">🧮 ${T('Calculators','Калькуляторы')}</a></div>
  <div class="grid cols-2 sheet-layout" style="gap:18px">
    <div>
      <div class="panel mb">
        <h2>📊 ${T('General Difficulty','Общая сложность')}</h2>
        <div class="statgrid">${genDv.map(([n,d])=>'<div class="stat"><div class="v">'+d+'</div><div class="k">'+esc(n)+'</div></div>').join('')}</div>
      </div>
      <div class="panel mb">
        <h2>💀 ${T('Wound Penalties','Штрафы ранений')}</h2>
        <div class="kv">
          <div><b>${T('Seriously Wounded','Серьёзное')}</b><span class="small muted">HP ≤ ½ max → −2 to all Actions</span></div>
          <div><b>${T('Mortally Wounded','Смертельное')}</b><span class="small muted">HP < 1 → −4 Actions, −6 MOVE, Death Save</span></div>
        </div>
      </div>
    </div>
    <div>
      <div class="panel mb">
        <h2>⚔️ ${T('Combat Actions','Боевые действия')}</h2>
        <div class="kv">${actions.map(([n,d])=>'<div><b>'+esc(n)+'</b><span class="small muted">'+esc(d)+'</span></div>').join('')}</div>
      </div>
      <div class="panel mb">
        <h2>🛡️ ${T('Armor Rules','Правила брони')}</h2>
        <div class="kv">
          <div><b>SP vs Damage</b><span class="small muted">${T('Damage > SP = pierced, SP ablates 1. Else holds.','Урон > SP = пробито, SP −1. Иначе держит.')}</span></div>
          <div><b>${T('Melee','Ближний бой')}</b><span class="small muted">${T('Target SP ÷ 2 (round up)','SP цели ÷ 2 (вверх)')}</span></div>
          <div><b>${T('Critical Injury','Крит. травма')}</b><span class="small muted">${T('2+ sixes → +5 HP (armor ignored) + 2d6 location','2+ шестёрки → +5 HP (броня игнорируется) + 2d6 локация')}</span></div>
        </div>
      </div>
    </div>
  </div>`;
}
