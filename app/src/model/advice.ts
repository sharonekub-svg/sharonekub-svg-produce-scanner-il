// General storage guidance per produce type (ux-principles.md #7). This is generic food-storage
// advice, NOT a claim about the photographed item, and the UI labels it "כללי".
export const STORAGE_TIP_HE: Record<string, string> = {
  banana: 'לשמור בטמפרטורת החדר, בנפרד משאר הפירות. אחרי שהבשילה אפשר לקרר – הקליפה תשחים, הפרי נשאר טוב.',
  avocado: 'להבשלה – בטמפרטורת החדר (שקית נייר מזרזת). אחרי שהבשיל – במקרר, לכמה ימים.',
  tomato: 'בטמפרטורת החדר, הרחק משמש ישירה. קירור פוגע בטעם.',
  apple: 'במקרר, במגירת הירקות – נשמר טרי לאורך זמן.',
  orange: 'במקום קריר או במקרר, לא בשקית סגורה.',
  mandarin: 'במקום קריר או במקרר, לא בשקית סגורה.',
  lemon: 'במקרר, במגירת הירקות.',
  cucumber: 'במקרר, עטוף, הרחק מבננות ועגבניות.',
  mango: 'להבשלה – בטמפרטורת החדר. אחרי שהבשיל – במקרר.',
  peach: 'להבשלה – בטמפרטורת החדר. אחרי שהבשיל – במקרר ולאכול בהקדם.',
  nectarine: 'להבשלה – בטמפרטורת החדר. אחרי שהבשיל – במקרר ולאכול בהקדם.',
  plum: 'להבשלה – בטמפרטורת החדר. אחרי שהבשיל – במקרר.',
  kiwi: 'להבשלה – בטמפרטורת החדר. אחרי שהבשיל – במקרר.',
  pear: 'להבשלה – בטמפרטורת החדר. אחרי שהבשיל – במקרר.',
  persimmon: 'להבשלה – בטמפרטורת החדר. אחרי שהתרכך – במקרר.',
  guava: 'בטמפרטורת החדר עד שמתרככת, אחר כך במקרר.',
  strawberry: 'במקרר. לשטוף רק לפני האכילה.',
  grape: 'במקרר. לשטוף רק לפני האכילה.',
  watermelon: 'שלם – בטמפרטורת החדר. חתוך – במקרר, מכוסה.',
  melon: 'שלם – בטמפרטורת החדר עד שמבשיל. חתוך – במקרר, מכוסה.',
  pomegranate: 'במקום קריר או במקרר – נשמר זמן רב.',
  pepper: 'במקרר, במגירת הירקות.',
};

/** Confidence in words first, calibrated number second (ux-principles.md #5). */
export function confidenceWord(p: number | null | undefined): string {
  if (p == null) return '';
  if (p >= 0.85) return 'ביטחון גבוה';
  if (p >= 0.7) return 'ביטחון בינוני';
  return 'ביטחון נמוך';
}

/** Combine two photos of the same fruit: normalised geometric mean of the per-head
 *  probabilities (product of experts). Used only for the optional "another angle" retry. */
export function combineProbs(a: number[], b: number[]): number[] {
  const g = a.map((v, i) => Math.sqrt(Math.max(v, 1e-12) * Math.max(b[i], 1e-12)));
  const s = g.reduce((x, y) => x + y, 0);
  return g.map((v) => v / s);
}
