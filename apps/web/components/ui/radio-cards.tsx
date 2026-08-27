"use client";

/**
 * A radiogroup of cards — one choice among a handful, each with a description.
 *
 * 🔴 IT EXISTS BECAUSE `role="radiogroup"` IS A PROMISE ABOUT THE KEYBOARD.
 *
 * The settings screen declared two of them over rows of ordinary buttons, with
 * a comment saying arrow-key navigation "is what a screen reader user expects
 * from a radiogroup and does not get from a row of buttons" — and then did not
 * implement it. So the role announced a widget whose keyboard behaviour was
 * absent: every option was a separate tab stop, arrow keys did nothing, and a
 * screen reader told the user to press arrows that had no effect. The
 * Supervisor found it. That is worse than the plain buttons the comment was
 * arguing against, because the plain buttons at least behave the way they are
 * announced.
 *
 * ⚠️ SELECTION FOLLOWS FOCUS, which is the WAI-ARIA radiogroup pattern and not
 * an oversight. Arrowing to an option chooses it. That is right here for the
 * same reason the screen has no Save button: both choices apply immediately and
 * are reversible in one keystroke, so there is nothing to confirm.
 *
 * 🔴 ROVING TABINDEX, so the group is ONE tab stop rather than five. Five
 * separate stops in the middle of a settings page is exactly the keyboard
 * treacle §11 exists to prevent, and it is what the previous buttons did.
 */

import { useRef } from "react";

export interface RadioCardOption<T extends string> {
  readonly id: T;
  readonly label: string;
  /** One line a person can choose by, not a restatement of the label. */
  readonly description: string;
  /** Optional visual, e.g. a palette swatch. Decorative; never the only cue. */
  readonly preview?: React.ReactNode;
}

const TAG =
  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
  "tracking-wide text-slate-600";

export function RadioCards<T extends string>({
  labelledBy,
  options,
  value,
  onChange,
}: {
  readonly labelledBy: string;
  readonly options: readonly RadioCardOption<T>[];
  readonly value: T;
  readonly onChange: (next: T) => void;
}) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (from: number, delta: number) => {
    // Wrapping, because a radiogroup is a ring: arrowing past the end of five
    // options and stopping dead reads as a broken control rather than a
    // boundary.
    const next = (from + delta + options.length) % options.length;
    const option = options[next];
    if (option === undefined) return;
    onChange(option.id);
    buttons.current[next]?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowRight":
        event.preventDefault();
        move(index, 1);
        break;
      case "ArrowUp":
      case "ArrowLeft":
        event.preventDefault();
        move(index, -1);
        break;
      case "Home":
        event.preventDefault();
        move(index, -index);
        break;
      case "End":
        event.preventDefault();
        move(index, options.length - 1 - index);
        break;
      default:
        break;
    }
  };

  return (
    <div role="radiogroup" aria-labelledby={labelledBy} className="mt-3 grid gap-2">
      {options.map((option, index) => {
        const chosen = option.id === value;
        return (
          <button
            key={option.id}
            ref={(element) => {
              buttons.current[index] = element;
            }}
            type="button"
            role="radio"
            aria-checked={chosen}
            // 🔴 THE GROUP IS ONE TAB STOP. Only the selected option is
            // reachable by Tab; the arrows move within. A group where every
            // option is tabbable is the thing this component replaced.
            tabIndex={chosen ? 0 : -1}
            onClick={() => onChange(option.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={[
              "flex items-center gap-3 rounded border p-3 text-left",
              chosen
                ? "border-slate-900 bg-slate-50"
                : "border-slate-200 bg-white hover:bg-slate-50",
            ].join(" ")}
          >
            {option.preview}
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-slate-900">{option.label}</span>
              <span className="block text-xs text-slate-600">{option.description}</span>
            </span>
            {/* 🔴 A WORD, NOT A TICK ALONE. §11 forbids state carried by colour
                or shape alone, and "which one is selected" is state.
                `aria-checked` says it assistively; this says it to everyone
                else. */}
            {chosen && <span className={TAG}>selected</span>}
          </button>
        );
      })}
    </div>
  );
}
