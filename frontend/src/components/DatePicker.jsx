import React, { useMemo, useRef, useState, useEffect } from 'react';

function pad(n) {
  return n < 10 ? `0${n}` : `${n}`;
}

function toISO(y, m, d) {
  return `${y}-${pad(m + 1)}-${pad(d)}`;
}

function parseISO(iso) {
  if (!iso) return null;
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

const months = [
  'Enero','Febrero','Marzo','Abril','Mayo','Junio',
  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'
];

function formatDisplay(iso) {
  const d = parseISO(iso);
  if (!d) return '';
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

export default function DatePicker({ id, label = 'Fecha', value, onChange, max, min, placeholder = 'dd/mm/aaaa' }) {
  const today = useMemo(() => new Date(), []);
  const maxDate = useMemo(() => (max ? parseISO(max) : today), [max, today]);
  const minDate = useMemo(() => (min ? parseISO(min) : new Date(1900, 0, 1)), [min]);

  const initial = parseISO(value) || maxDate;
  const [open, setOpen] = useState(false);
  const [viewYear, setViewYear] = useState(initial.getFullYear());
  const [viewMonth, setViewMonth] = useState(initial.getMonth());
  const [hintDate, setHintDate] = useState(null);

  const ref = useRef(null);
  const [text, setText] = useState(formatDisplay(value));

  useEffect(() => {
    setText(formatDisplay(value));
  }, [value]);

  useEffect(() => {
    function onDocClick(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const weeks = useMemo(() => {
    const first = new Date(viewYear, viewMonth, 1);
    const last = new Date(viewYear, viewMonth + 1, 0);
    const startDay = first.getDay(); // 0 Sun .. 6 Sat
    const daysInMonth = last.getDate();
    const cells = [];
    // Leading blanks
    for (let i = 0; i < startDay; i++) cells.push(null);
    // Month days
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    // Pad to full weeks
    while (cells.length % 7 !== 0) cells.push(null);
    const rows = [];
    for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));
    return rows;
  }, [viewYear, viewMonth]);

  function goPrevMonth() {
    let m = viewMonth - 1;
    let y = viewYear;
    if (m < 0) { m = 11; y -= 1; }
    setViewMonth(m); setViewYear(y);
  }

  function goNextMonth() {
    let m = viewMonth + 1;
    let y = viewYear;
    if (m > 11) { m = 0; y += 1; }
    setViewMonth(m); setViewYear(y);
  }

  function isDisabled(d) {
    if (d == null) return true;
    const dt = new Date(viewYear, viewMonth, d);
    return dt < minDate || dt > maxDate;
  }

  function isSelected(d) {
    if (!value) return false;
    const sel = parseISO(value);
    return sel && sel.getFullYear() === viewYear && sel.getMonth() === viewMonth && sel.getDate() === d;
  }

  function pick(d) {
    if (isDisabled(d)) return;
    const iso = toISO(viewYear, viewMonth, d);
    onChange?.(iso);
    setOpen(false);
  }

  useEffect(() => {
    // If navigating months beyond max/min, clamp navigation buttons
  }, [viewMonth, viewYear, maxDate, minDate]);

  // Helpers to compute a hint date from partial user input without requiring Enter
  function lastValidDateWithDay(day) {
    let y = maxDate.getFullYear();
    let m = maxDate.getMonth();
    // search backward up to 240 months (~20 years) just to be safe
    for (let i = 0; i < 240; i++) {
      const d = new Date(y, m, Number(day));
      if (d.getMonth() === m && d.getDate() === Number(day) && d <= maxDate && d >= minDate) {
        return d;
      }
      // step back one month
      m -= 1;
      if (m < 0) { m = 11; y -= 1; }
      if (new Date(y, m, 1) < minDate) break;
    }
    return null;
  }

  function lastValidDateWithDayMonth(day, month) {
    let y = maxDate.getFullYear();
    const mm = Number(month) - 1;
    for (let i = 0; i < 200; i++) {
      const d = new Date(y, mm, Number(day));
      if (d.getMonth() === mm && d.getDate() === Number(day) && d <= maxDate && d >= minDate) {
        return d;
      }
      y -= 1;
      if (new Date(y, mm, 1) < minDate) break;
    }
    return null;
  }

  // Parse from user text input (partial aware) and return a Date hint
  function deriveHintFromText(t) {
    if (!t) return null;
    const onlyDay = /^\s*(\d{1,2})\s*$/;
    const dayMonth = /^\s*(\d{1,2})[\/](\d{1,2})\s*$/;
    const ddmmyyyy = /^\s*(\d{1,2})[\/](\d{1,2})[\/]((?:19|20)\d{2})\s*$/;
    const yyyymmdd = /^\s*((?:19|20)\d{2})-(\d{1,2})-(\d{1,2})\s*$/;

    if (onlyDay.test(t)) {
      const [, dd] = t.match(onlyDay);
      return lastValidDateWithDay(dd);
    }
    if (dayMonth.test(t)) {
      const [, dd, mm] = t.match(dayMonth);
      return lastValidDateWithDayMonth(dd, mm);
    }
    let d = null;
    if (ddmmyyyy.test(t)) {
      const [, dd, mm, yyyy] = t.match(ddmmyyyy);
      d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
    } else if (yyyymmdd.test(t)) {
      const [, yyyy, mm, dd] = t.match(yyyymmdd);
      d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
    }
    if (!d || isNaN(d.getTime())) return null;
    if (d < minDate || d > maxDate) return null;
    return d;
  }

  // Parse only complete formats for committing value
  function parseFromText(t) {
    if (!t) return null;
    const ddmmyyyy = /^\s*(\d{1,2})[\/](\d{1,2})[\/]((?:19|20)\d{2})\s*$/;
    const yyyymmdd = /^\s*((?:19|20)\d{2})-(\d{1,2})-(\d{1,2})\s*$/;
    let d = null;
    if (ddmmyyyy.test(t)) {
      const [, dd, mm, yyyy] = t.match(ddmmyyyy);
      d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
    } else if (yyyymmdd.test(t)) {
      const [, yyyy, mm, dd] = t.match(yyyymmdd);
      d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
    }
    if (!d || isNaN(d.getTime())) return null;
    if (d < minDate || d > maxDate) return null;
    return d;
  }

  function onInputBlur() {
    const d = parseFromText(text);
    if (d) {
      onChange?.(toISO(d.getFullYear(), d.getMonth(), d.getDate()));
      setHintDate(null);
    }
  }

  return (
    <div className="datepicker" ref={ref}>
      {label && <label className="muted" htmlFor={id}>{label}</label>}
      <div className="datepicker-trigger" onClick={() => setOpen(o => !o)} role="button" tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setOpen(o => !o); }}>
        <input
          id={id}
          className="input"
          value={text}
          onChange={(e) => {
            const t = e.target.value;
            setText(t);
            const hint = deriveHintFromText(t);
            if (hint) {
              setViewYear(hint.getFullYear());
              setViewMonth(hint.getMonth());
              setHintDate(hint);
            } else {
              setHintDate(null);
            }
          }}
          onBlur={onInputBlur}
          placeholder={placeholder}
        />
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="icon">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="16" y1="2" x2="16" y2="6"></line>
          <line x1="8" y1="2" x2="8" y2="6"></line>
          <line x1="3" y1="10" x2="21" y2="10"></line>
        </svg>
      </div>

      {open && (
        <div className="datepicker-pop card">
          <div className="datepicker-head">
            <button className="btn" onClick={goPrevMonth} aria-label="Mes anterior">◀</button>
            <div className="month-title">{months[viewMonth]} {viewYear}</div>
            <button className="btn" onClick={goNextMonth} aria-label="Mes siguiente">▶</button>
          </div>
          <div className="datepicker-grid">
            {['D','L','M','X','J','V','S'].map((d,i) => (
              <div key={`h-${i}`} className="cell head">{d}</div>
            ))}
            {weeks.map((row, ri) => (
              row.map((d, ci) => {
                const disabled = isDisabled(d);
                const selected = isSelected(d);
                const hinted = (() => {
                  if (!hintDate || d == null) return false;
                  return hintDate.getFullYear() === viewYear && hintDate.getMonth() === viewMonth && hintDate.getDate() === d;
                })();
                return (
                  <button
                    key={`c-${ri}-${ci}`}
                    className={`cell ${disabled ? 'disabled' : ''} ${selected ? 'selected' : ''} ${!selected && hinted ? 'hint' : ''}`}
                    onClick={() => pick(d)}
                    disabled={disabled}
                  >
                    {d || ''}
                  </button>
                );
              })
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
