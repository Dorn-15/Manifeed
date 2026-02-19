export type SourceDateFormat = "full" | "time" | "day_month" | "day_month_year" | "split";

type SourceDateSplit = {
  date: string;
  time: string;
};

const FALLBACK_VALUE = "n/a";

function parseIsoDate(isoDate: string | null): Date | null {
  if (!isoDate) {
    return null;
  }

  const parsedDate = new Date(isoDate);
  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return parsedDate;
}

function formatWithOptions(date: Date, locale: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(locale, options).format(date);
}

function formatSourceDateFull(date: Date, locale: string): string {
  return formatWithOptions(date, locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatSourceDateTime(date: Date, locale: string): string {
  return formatWithOptions(date, locale, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSourceDateDayMonth(date: Date, locale: string): string {
  return formatWithOptions(date, locale, {
    day: "numeric",
    month: "numeric",
  });
}

function formatSourceDateDayMonthYear(date: Date, locale: string): string {
  return formatWithOptions(date, locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatSourceDate(
  isoDate: string | null,
  format: "split",
  locale?: string,
): SourceDateSplit;
export function formatSourceDate(
  isoDate: string | null,
  format?: Exclude<SourceDateFormat, "split">,
  locale?: string,
): string;
export function formatSourceDate(
  isoDate: string | null,
  format: SourceDateFormat = "full",
  locale: string = "fr-FR",
): string | SourceDateSplit {
  const parsedDate = parseIsoDate(isoDate);
  if (!parsedDate) {
    if (format === "split") {
      return { date: FALLBACK_VALUE, time: FALLBACK_VALUE };
    }
    return FALLBACK_VALUE;
  }

  if (format === "time") {
    return formatSourceDateTime(parsedDate, locale);
  }

  if (format === "day_month") {
    return formatSourceDateDayMonth(parsedDate, locale);
  }

  if (format === "day_month_year") {
    return formatSourceDateDayMonthYear(parsedDate, locale);
  }

  if (format === "split") {
    return {
      date: formatSourceDateDayMonthYear(parsedDate, locale),
      time: formatSourceDateTime(parsedDate, locale),
    };
  }

  return formatSourceDateFull(parsedDate, locale);
}
