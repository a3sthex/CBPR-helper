/* Product localization. Guides intentionally remain in their original Russian. */
'use strict';

const APP_I18N = (() => {
  const STORAGE_KEY = 'cbpr-helper:language';
  const RU_EN = {
    'Закрыть':'Close','Загрузка…':'Loading…','Нет данных':'No data','Безымянный':'Unnamed','Тело':'Body','Голова':'Head','Щит':'Shield',
    'Создать персонажа':'Create Character','Создание персонажа':'Character Creation','Чёрный рынок':'Night Market','Справочник':'Codex','Калькулятор':'Calculator',
    'Мои персонажи':'My Characters','Новый эджраннер':'New Edgerunner','Ростер партии':'Campaign Roster','Сводки с улиц':'Street Reports','Горячие заказы':'Hot Jobs','Доска заказов':'Job Board',
    'все новости →':'all news →','вся доска →':'full board →','Всё подряд':'All Categories','Найти':'Search','Описание':'Description','Описание отсутствует.':'No description available.',
    'Назад':'Back','Вперёд →':'Next →','Удалить':'Delete','Удалено':'Removed','Сохранить':'Save','Сохранено ✓':'Saved ✓','Редактировать':'Edit','Открыть':'Open',
    'Добавить':'Add','Выбрать':'Choose','Отмена':'Cancel','Купить':'Buy','Продать':'Sell','Фильтр':'Filter','Поиск':'Search','Категория':'Category','Источник':'Source',
    'Цена':'Price','Количество':'Quantity','Осталось':'Remaining','Потрачено':'Spent','Наличные':'Cash','Характеристики':'Characteristics','Навыки':'Skills','Внешность':'Appearance',
    'Предыстория':'Background','Языки':'Languages','Жизнь':'Lifestyle','Заметки':'Notes','Инвентарь':'Inventory','Броня':'Armor','Хром':'Cyberware','Оружие':'Weapons',
    'Роль':'Role','Ранг роли':'Role Rank','Игрок':'Player','Публичный':'Public','Приватный':'Private','публичный':'public','приватный':'private','Владелец':'Owner',
    'Регистрация':'Register','Вход':'Sign In','Войти':'Sign In','Выйти':'Sign Out','Логин':'Username','Пароль':'Password','Профиль':'Profile','Создать аккаунт':'Create Account',
    'Отображаемое имя':'Display Name','Все публичные персонажи всех игроков.':'All public characters from every player.','Пока пусто.':'Nothing here yet.',
    'Пока никто не записался.':'No one has signed up yet.','Вы записаны ✓':'You are signed up ✓','Отменить запись':'Cancel Signup','Записаться':'Sign Up','без персонажа':'without a character',
    'Опубликовать':'Publish','Заголовок':'Title','Текст':'Body','Автор':'Author','Статус':'Status','Открыт':'Open','Закрыт':'Closed','Слоты':'Slots','Без ограничений':'Unlimited',
    'Основное':'General','Снаряжение и оружие':'Gear & Weapons','Кибернетика':'Cyberware','Прочее':'Other','Текущее HP':'Current HP','Текущая человечность':'Current Humanity',
    'Бюджет':'Budget','Требования':'Requirements','Не хватает':'Not enough','Купить выбранное':'Buy Selected','Очистить':'Clear','Корзина':'Cart','Склад':'Inventory',
    'Урон':'Damage','Бросок':'Roll','Критические травмы':'Critical Injuries','Автоогонь':'Autofire','Дальность':'Range','Состояние':'State','Порог':'Threshold','Эффект':'Effect','Стабилизация':'Stabilization',
    'Культурный язык':'Cultural Language','Обязательные навыки':'Required Skills','Рекомендуемые':'Recommended','Распределено':'Allocated','Свободно':'Free','Уровень':'Level',
    'Мини-гайды':'Mini Guides','Гайды не загрузились':'Guides failed to load','Russian only':'Russian only',
    'Персонаж удалён':'Character deleted','Вы вышли из системы.':'Signed out.','Тема сохранена.':'Theme saved.','Draft очищен.':'Draft cleared.',
    'Не выбрано':'Not selected','не выбрано':'not selected','— не выбрано —':'— not selected —','Чист от хрома. Пока что.':'No Cyberware installed.','Пусто. Совсем.':'Empty.',
    'Имя (необязательно)':'First Name (optional)','Фамилия (необязательно)':'Last Name (optional)','Культурный':'Cultural','бесплатно':'free','обязательно':'required',
  };
  // Legacy templates still contain Russian literals. Keep these translations at the
  // display boundary; saved values and user-authored text are never rewritten.
  Object.assign(RU_EN, {
    'Ночной город':'Night City','онлайн':'online','Персонажи':'Characters','Персонаж':'Character','Лист персонажа':'Character Sheet',
    'Горячие заказы':'Hot Jobs','Все категории':'All Categories','Поиск по каталогу…':'Search the catalog…','Поиск…':'Search…','Поиск навыков…':'Search Skills…',
    'Поиск по названию, описанию или Type…':'Search by name, description, or Type…','Найти в Cyberware':'Find in Cyberware','Найти совместимые боеприпасы':'Find Compatible Ammo',
    'Ночная витрина':'Night Market Showcase','Полный каталог':'Full Catalog','Скупка хлама':'Sell Used Gear','В корзину':'Add to Cart','ВЫГОДНО':'DEAL','переплата':'markup',
    'Все категории':'All Categories','Нет товаров с ценой по этому запросу.':'No priced items matched this search.','Войдите, чтобы продавать хлам со склада своих персонажей.':'Sign in to sell items from your characters’ inventories.',
    'Нет персонажей.':'No characters.','Создать первого':'Create the first one','Инвентарь пуст.':'Inventory is empty.','Добавлено в корзину:':'Added to Cart:','Корзина:':'Cart:',
    'Сначала войдите в систему':'Sign in first','Сначала создайте персонажа':'Create a character first','Оформление покупки':'Complete Purchase','Итого:':'Total:','Покупатель':'Buyer',
    'Выплата / списание (ГМ)':'Payout / Deduction (GM)','Выплата (ГМ)':'Payout (GM)','Начислить или списать евробаксы любому персонажу — награда за заказ, штраф или аванс.':'Add or deduct eurobucks for any character as a Job reward, penalty, or advance.',
    'Сумма (€$, минус — списать)':'Amount (€$; use a minus sign to deduct)','Провести':'Apply','Готово. Теперь на счету:':'Done. New balance:',
    'Расчёт урона':'Damage Calculation','Формула урона':'Damage Formula','брони цели':'target Armor','цели':'target','Текущее HP цели':'Target Current HP',
    'Ближний бой / бронепробой (SP цели делится на 2, округление вверх)':'Melee / Armor Piercing (target SP is halved, rounded up)','Броски костей':'Dice Rolls',
    'Несколько слоёв брони':'Multiple Armor Layers','Критические травмы':'Critical Injuries','Бросить 2d6 — тело':'Roll 2d6 — Body','Бросить 2d6 — голова':'Roll 2d6 — Head',
    'Таблицы травм':'Injury Tables','Автоогонь':'Autofire','Тип оружия':'Weapon Type','Бросить атаку':'Roll Attack','Спасбросок от смерти':'Death Save',
    'Штраф (Death Save Penalty)':'Death Save Penalty','Бросить 1d10':'Roll 1d10','Состояния ранений':'Wound States','Таблица DV (дальность)':'DV Table (Range)',
    'Таблица DV (автоогонь)':'DV Table (Autofire)','Не понял формулу':'Formula not recognized','Действующий SP:':'Effective SP:','Состояние':'State','Порог':'Threshold','Стабилизация':'Stabilization',
    'Выберите роль и настройте преимущества Rank 4.':'Choose a Role and configure its Rank 4 benefits.','Создайте личность, происхождение, ценности и Role-Based Lifepath.':'Create an identity, origin, values, and Role-Based Lifepath.',
    'Распределите ровно 62 очка':'Allocate exactly 62 points','каждая характеристика от 2 до 8.':'each Characteristic must be between 2 and 8.','Распределите 86 очков между навыками и специализациями Corebook.':'Allocate 86 points among Corebook Skills and specializations.',
    'Закупка':'Shopping','Соберите стартовое снаряжение, Fashion и Cyberware.':'Assemble starting Gear, Fashion, and Cyberware.','Итог':'Summary','Исправьте ошибки и проверьте готовый Character Sheet.':'Resolve errors and review the finished Character Sheet.',
    'Выберите роль':'Choose a Role','Предыдущая роль':'Previous Role','Следующая роль':'Next Role','Кто вы':'Who You Are','Стиль игры':'Play Style','Полная справка способности':'Full Ability Reference',
    'Используйте вкладки, клавиши-стрелки, кнопки или свайп.':'Use the tabs, arrow keys, buttons, or a swipe gesture.','не выбрано —':'not selected —','Случайный результат':'Random Result',
    'Общий Lifepath':'Common Lifepath','Ролевой':'Role-Based','выберите роль':'choose a Role','Заполнить пустые':'Fill Missing','Перебросить всё':'Reroll All','Заменить':'Replace',
    'Загрузить портрет персонажа':'Upload Character Portrait','Мужское':'Masculine','Женское':'Feminine','Нейтральное':'Neutral','Сгенерировать имя':'Generate Full Name',
    'Культурный язык · уровень 4 бесплатно':'Cultural Language · Level 4 free','Сначала выберите регион':'Choose a region first','Сначала выберите роль':'Choose a Role first','Перейти к роли':'Go to Role',
    'Связанные навыки':'Related Skills','Сгенерировать незакреплённые':'Generate Unlocked','Рекомендуемые приоритеты для':'Recommended priorities for','Сохранить при генерации':'Keep During Generation','Диапазон':'Range',
    'Описание навыка пока не добавлено.':'No Skill description has been added yet.','ГМ определяет подходящий пример и сложность проверки.':'The GM determines an appropriate example and check difficulty.',
    'Пример':'Example','Добавить специализацию':'Add Specialization','Название специализации':'Specialization Name','Культурный 4 бесплатно':'Cultural Level 4 free','оплачено':'paid','авто':'auto',
    'Удалить специализацию':'Remove Specialization','Осознание':'Awareness','Управление':'Control Skills','Образование':'Education','Бой':'Fighting','Выступление':'Performance','Стрелковое':'Ranged Weapon',
    'Социальные':'Social','Технические':'Technique','Рекомендуется':'Recommended','Ролевая способность — не навык':'Role Ability — not a Skill','Открыть роль':'Open Role',
    'Все':'All','Обязательные':'Required','Купленные':'Purchased','Нет навыков по выбранным фильтрам.':'No Skills match the selected filters.','Другое':'Other','Предмет':'Item',
    'Описание в Data Pool не указано.':'No description is provided in the Data Pool.','Не хватает бюджета стиля (800€$)':'Not enough Style Budget (800eb)','Добавлено:':'Added:',
    'Бюджет стиля:':'Style Budget:','Остаток сгорает после создания':'Unused funds are lost after creation','Фильтр одежды и Fashionware…':'Filter Clothing and Fashionware…','Одежда · по Type':'Clothing · by Type',
    'Выбранный стиль':'Selected Style','Пока ничего не выбрано.':'Nothing selected yet.','комплект голова + тело':'Head + Body set','щит':'shield','за покупку':'per purchase',
    'Выберите host':'Choose a host','Установить':'Install','Требуется доступный':'Requires available','Выберите минимум два предмета.':'Choose at least two items.','Сравнение предметов':'Compare Items',
    'выбранный транспорт':'selected vehicle','выбранный Cyberdeck':'selected Cyberdeck','Совместимо с выбранным снаряжением':'Compatible with selected Gear','Показать Foundations':'Show Foundations',
    'Ничего не найдено.':'Nothing found.','Можно сравнить не более трёх предметов.':'You can compare no more than three items.','Не надета броня для тела':'No Body Armor equipped','Не надета броня для головы':'No Head Armor equipped',
    'Не удалось подобрать комплект.':'Could not build an outfit.','Надеть':'Equip','Стартовое снаряжение не выбрано.':'No starting Gear selected.','Выбран':'Selected','Выбрать':'Select','Куплен':'Purchased',
    'Что вы им должны?':'What do you owe them?','Доступные':'Available','Выбранные':'Selected','Создать комплект':'Generate Outfit','Выбранное снаряжение':'Selected Gear','боеприпасы':'ammo',
    'Роль: выберите роль':'Role: choose a Role','Не заполнен общий Lifepath':'Common Lifepath is incomplete','Закупка: превышен основной бюджет':'Shopping: Main Budget exceeded',
    'Закупка: превышен Style Budget':'Shopping: Style Budget exceeded','Допустим только один Neuroport':'Only one Neuroport is allowed','Для Cyberware нужен Neuroport':'Cyberware requires a Neuroport',
    'чист от хрома —':'no Cyberware —','Нет':'None','Нет Cyberware':'No Cyberware','Неиспользованный Style Budget сгорит':'Unused Style Budget will be lost','блокирующих ошибок':'blocking errors',
    'Готов к созданию':'Ready to Create','предупреждений':'warnings','Исправить':'Fix','Все проверки пройдены.':'All checks passed.','Роль не выбрана':'No Role selected','Изменить роль':'Change Role',
    'Не заполнен':'Incomplete','Изменить Lifepath':'Edit Lifepath','Показывать навыки уровня 0':'Show Level 0 Skills','Оружие не выбрано':'No Weapons selected','Стартовые наличные':'Starting Cash','Сгорит':'Will be lost',
    'Характеристики сброшены.':'Characteristics reset.','Пустые поля Lifepath заполнены.':'Missing Lifepath fields filled.','Заменить все результаты Lifepath?':'Replace every Lifepath result?',
    'Недостаточно очков для увеличения parent-pool.':'Not enough points to increase the parent pool.','Создание…':'Creating…','Персонаж создан!':'Character created!',
    'владелец':'owner','игрок':'player','Серьёзная рана':'Seriously Wounded','Человечность':'Humanity','Надетая броня':'Equipped Armor','Жильё':'Housing',
    'Раздел только для вошедших.':'This section requires sign-in.','Личное хранилище':'Personal Storage','Пока пусто. Создай первого эджраннера — процесс займёт пару минут.':'Nothing here yet. Create your first edgerunner in a few minutes.',
    'Редактор:':'Editor:','Это персонаж игрока':'This character belongs to player','Смотреть его можно в':'You can view them in the','ростере':'Roster','К моим':'My Characters',
    'макс':'max','текущий':'current','Штраф брони':'Armor Penalty','Псевдоним (Handle) *':'Handle *','Игрок (реальное имя)':'Player (real name)','Биография / предыстория':'Biography / Background',
    'Счёт (€$)':'Balance (€$)','Текущее HP (пусто = максимум)':'Current HP (blank = maximum)','Текущая человечность (пусто = максимум)':'Current Humanity (blank = maximum)',
    'без специализации':'without specialization','родной':'native','Специализированные навыки':'Specialized Skills','Нет специализированных навыков.':'No specialized Skills.',
    'Базовый навык: Language, Local Expert, Martial Arts, Science или Play Instrument':'Parent Skill: Language, Local Expert, Martial Arts, Science, or Play Instrument',
    'Конкретный язык, район, стиль, наука или инструмент':'A specific language, area, style, science, or instrument','Всё купленное на рынке тоже попадает сюда.':'Everything purchased at the Market also appears here.',
    'Снаряжение (все категории)':'Gear (all categories)','Вшить хром':'Install Cyberware','русский, английский…':'Russian, English…','Показывать персонажа в общем ростере партии':'Show this character in the public Campaign Roster',
    'Пусто. Совсем. Даже пушки нет.':'Completely empty. Not even a gun.','Ты ещё чист от хрома. Пока что.':'No Cyberware installed. Yet.','вырезать':'remove','пусто —':'empty —','Выбрать броню':'Choose Armor',
    'Все публичные персонажи.':'All public characters.','Фильтр: псевдоним, роль, игрок…':'Filter by Handle, Role, or player…','Никого. Пока что.':'No one here yet.',
    'Внешность:':'Appearance:','Биография:':'Biography:','События партий от разных источников.':'Game events from multiple sources.','Перестрелка в Мегабилдинге H4':'Shootout in Megabuilding H4',
    'Источник / тег (партия, район…)':'Source / tag (game, district…)','Что случилось':'What happened','Кратко: кто, где, чем кончилось…':'Briefly: who, where, and how it ended…',
    'Опубликовано':'Published','Войди, чтобы публиковать сводки.':'Sign in to publish reports.','Сводок нет. Улицы молчат.':'No reports. The streets are quiet.','Удалить сводку?':'Delete this report?',
    'ГМ публикует партии':'GMs post games','Эджраннеры записываются.':'Edgerunners sign up.','Разместить заказ':'Post a Job','Размещать заказы могут пользователи с ролью ГМ (включается в профиле).':'Users with the GM role can post Jobs (enabled in Profile).',
    'Подробнее / записаться':'Details / Sign Up','вы записаны':'you are signed up','Заказов нет. ГМ, разместите первый!':'No Jobs yet. GM, post the first one!','Удалить заказ?':'Delete this Job?',
    'Новый заказ':'New Job','Название':'Title','Ограбление конвоя Милитех':'Rob a Militech Convoy','Когда':'When','Слотов (0 = без лимита)':'Slots (0 = unlimited)','Система':'System',
    'Сеттинг, состав, что взять с собой, куда подходить…':'Setting, crew, what to bring, and where to meet…','Разместить':'Post','Заказ размещён':'Job posted','Пока никто не записался.':'No one has signed up yet.',
    'Запись отменена':'Signup canceled','без персонажа —':'without a character —','Вы записаны! ГМ свяжется.':'You are signed up! The GM will contact you.','Войдите, чтобы записаться.':'Sign in to sign up.',
    'Логин (латиница)':'Username (Latin letters)','Как тебя знают в городе':'How Night City knows you','Я ГМ (могу размещать заказы и вести выплаты)':'I am a GM (can post Jobs and issue payouts)',
    'С возвращением,':'Welcome back,','Добро пожаловать в Ночной город.':'Welcome to Night City.','Профиль обновлён':'Profile updated',
  });
  const DYNAMIC = [
    [/^Найдено:\s*(.+)$/,'Found: $1'],[/^Личное хранилище:\s*(.+)$/,'Personal storage: $1'],[/^предметов$/,'items'],[/^персонажей$/,'characters'],[/^эджраннеров$/,'edgerunners'],[/^новостей$/,'reports'],[/^открытых заказов$/,'open jobs'],
    [/^слотов:\s*(.+)$/,'slots: $1'],[/^записалось:\s*(.+)$/,'signed up: $1'],[/^ГМ:\s*(.+)$/,'GM: $1'],[/^игрок:\s*(.+)$/,'player: $1'],[/^владелец:\s*(.+)$/,'owner: $1'],
    [/^обновлён\s+(.+)$/,'updated $1'],[/^Осталось:\s*(.+)$/,'Remaining: $1'],[/^Остаток:\s*(.+)$/,'Balance: $1'],[/^Потрачено:\s*(.+)$/,'Spent: $1'],[/^Распределено:\s*(.+)$/,'Allocated: $1'],
    [/^Витрина на\s+(.+)\. Товаров:\s*(.+)\. Цены уличные — на них и покупай\.$/,'Showcase for $1. Items: $2. These are street prices.'],
    [/^В корзину ·\s*(.+)$/,'Add to Cart · $1'],[/^Купить за\s*(.+)$/,'Buy for $1'],[/^Купить\s*(.+)$/,'Buy $1'],[/^Продать 1 →\s*(.+)$/,'Sell 1 → $1'],[/^Продано\s+(.+)$/,'Sold $1'],
    [/^Кэш:\s*(.+)$/,'Cash: $1'],[/^Удалить\s+(.+)$/,'Remove $1'],[/^Добавлено:\s*(.+)$/,'Added: $1'],[/^Выбран\s+(.+)$/,'Selected $1'],[/^Куплен\s+(.+)$/,'Purchased $1'],
    [/^Сменить роль\s+(.+)\s+на\s+(.+)$/,'Change Role from $1 to $2'],[/^Сотрудник:\s*(.+)$/,'Team Member: $1'],[/^Ролевой Lifepath ·\s*(.+)$/,'Role-Based Lifepath · $1'],
    [/^Рекомендуемые приоритеты для\s+(.+)$/,'Recommended priorities for $1'],[/^Распределите ровно\s+(.+)$/,'Allocate exactly $1'],[/^Бюджет стиля:\s*(.+)$/,'Style Budget: $1'],
    [/^ГМ:\s*(.+)$/,'GM: $1'],[/^игрок:\s*(.+)$/,'player: $1'],[/^владелец:\s*(.+)$/,'owner: $1'],[/^Владелец:\s*(.+)$/,'Owner: $1'],[/^Роль:\s*(.+)$/,'Role: $1'],
    [/^Удалить персонажа навсегда\?$/,'Permanently delete this character?'],[/^Ничего не нашлось\.$/,'Nothing matched.'],[/^Пока тихо\.$/,'Quiet for now.'],
    [/^Серьёзная рана ≤\s*(.+)$/,'Seriously Wounded ≤ $1'],[/^Броня SP тело:\s*(.+)$/,'Body Armor SP: $1'],[/^Броня SP голова:\s*(.+)$/,'Head Armor SP: $1'],
    [/^Хром\s*\((.+)\)$/,'Cyberware ($1)'],[/^Инвентарь\s*\((.+)\)$/,'Inventory ($1)'],[/^Записались\s*\((.+)\)$/,'Signed Up ($1)'],
    [/^Не хватает бюджета\s*(.*)$/,'Insufficient Budget $1'],[/^Требуется:\s*(.+)$/,'Requires: $1'],[/^Неизвестный специализированный навык\s*(.+)$/,'Unknown specialized Skill $1'],
    [/^Сервер недоступен:\s*(.*)$/,'Server unavailable: $1'],
  ];
  let language = 'en';
  try { language = localStorage.getItem(STORAGE_KEY) === 'ru' ? 'ru' : 'en'; } catch (e) {}

  function text(en, ru) { return language === 'ru' ? ru : en; }
  function translate(raw) {
    if (language !== 'en' || !raw || !/[А-Яа-яЁё]/.test(raw)) return raw;
    const lead=(raw.match(/^\s*/)||[''])[0],tail=(raw.match(/\s*$/)||[''])[0],value=raw.trim();
    if (RU_EN[value]) return lead+RU_EN[value]+tail;
    for (const [pattern,replacement] of DYNAMIC) if(pattern.test(value)) return lead+value.replace(pattern,replacement)+tail;
    return raw;
  }
  function excluded(node) { const el=node.nodeType===1?node:node.parentElement;return !el||!!el.closest('#guide-box,[data-no-auto-translate],textarea,.user-content,.desc[data-user-content]'); }
  function apply(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-en][data-ru]').forEach(el => { el.textContent = language === 'ru' ? el.dataset.ru : el.dataset.en; });
    scope.querySelectorAll('[data-placeholder-en][data-placeholder-ru]').forEach(el => { el.placeholder = language === 'ru' ? el.dataset.placeholderRu : el.dataset.placeholderEn; });
    if(language==='en' && typeof document.createTreeWalker==='function'){
      const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode()))if(!excluded(node))node.nodeValue=translate(node.nodeValue);
      scope.querySelectorAll('[placeholder],[title],[aria-label]').forEach(el=>{if(excluded(el))return;for(const name of ['placeholder','title','aria-label'])if(el.hasAttribute(name))el.setAttribute(name,translate(el.getAttribute(name)));});
    }
    document.documentElement.lang = language;
    const button = document.querySelector('#language-toggle');
    if (button) { button.textContent = language === 'en' ? 'RU' : 'EN'; button.title = language === 'en' ? 'Переключить на русский' : 'Switch to English'; button.setAttribute('aria-label', button.title); }
  }
  function set(next) { language = next === 'ru' ? 'ru' : 'en'; try { localStorage.setItem(STORAGE_KEY, language); } catch (e) {} apply(); window.dispatchEvent(new CustomEvent('app-language-change', { detail: { language } })); }
  function toggle() { set(language === 'en' ? 'ru' : 'en'); }
  function current() { return language; }
  function untranslated(root){if(language!=='en')return[];const scope=root||document,out=[];const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode()))if(!excluded(node)&&/[А-Яа-яЁё]/.test(node.nodeValue))out.push(node.nodeValue.trim());scope.querySelectorAll('[placeholder],[title],[aria-label]').forEach(el=>{if(excluded(el))return;for(const name of ['placeholder','title','aria-label'])if(el.hasAttribute(name)&&/[А-Яа-яЁё]/.test(el.getAttribute(name)))out.push(`${name}: ${el.getAttribute(name)}`);});return [...new Set(out.filter(Boolean))];}
  return { text, apply, set, toggle, current, translate, untranslated };
})();

const T = (en, ru) => APP_I18N.text(en, ru);
