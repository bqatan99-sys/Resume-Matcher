/**
 * Keyword extraction and matching utilities for JD-Resume comparison.
 */

import type { ResumeData } from '@/components/dashboard/resume-component';

// Common English stop words to filter out
const STOP_WORDS = new Set([
  // Articles
  'a',
  'an',
  'the',
  // Pronouns
  'i',
  'me',
  'my',
  'myself',
  'we',
  'our',
  'ours',
  'ourselves',
  'you',
  'your',
  'yours',
  'yourself',
  'yourselves',
  'he',
  'him',
  'his',
  'himself',
  'she',
  'her',
  'hers',
  'herself',
  'it',
  'its',
  'itself',
  'they',
  'them',
  'their',
  'theirs',
  'themselves',
  'what',
  'which',
  'who',
  'whom',
  'this',
  'that',
  'these',
  'those',
  // Verbs (common)
  'am',
  'is',
  'are',
  'was',
  'were',
  'be',
  'been',
  'being',
  'have',
  'has',
  'had',
  'having',
  'do',
  'does',
  'did',
  'doing',
  'will',
  'would',
  'could',
  'should',
  'might',
  'must',
  'shall',
  'can',
  'need',
  'dare',
  'ought',
  'used',
  // Prepositions
  'a',
  'an',
  'the',
  'and',
  'but',
  'if',
  'or',
  'because',
  'as',
  'until',
  'while',
  'of',
  'at',
  'by',
  'for',
  'with',
  'about',
  'against',
  'between',
  'into',
  'through',
  'during',
  'before',
  'after',
  'above',
  'below',
  'to',
  'from',
  'up',
  'down',
  'in',
  'out',
  'on',
  'off',
  'over',
  'under',
  'again',
  'further',
  'then',
  'once',
  // Conjunctions
  'and',
  'but',
  'or',
  'nor',
  'so',
  'yet',
  'both',
  'either',
  'neither',
  'not',
  'only',
  // Common words
  'here',
  'there',
  'when',
  'where',
  'why',
  'how',
  'all',
  'each',
  'every',
  'both',
  'few',
  'more',
  'most',
  'other',
  'some',
  'such',
  'no',
  'nor',
  'not',
  'only',
  'own',
  'same',
  'so',
  'than',
  'too',
  'very',
  'just',
  'also',
  'now',
  'etc',
  'within',
  // Job posting common words (not meaningful keywords)
  'role',
  'position',
  'job',
  'work',
  'working',
  'team',
  'company',
  'looking',
  'seeking',
  'required',
  'requirements',
  'responsibilities',
  'qualifications',
  'preferred',
  'experience',
  'years',
  'year',
  'ability',
  'skills',
  'knowledge',
  'strong',
  'excellent',
  'good',
  'great',
  'well',
  'include',
  'including',
  'includes',
  'must',
  'may',
  'like',
  'etc',
  'e.g',
  'i.e',
  'such',
  'via',
]);

// Minimum word length to consider as keyword
const MIN_WORD_LENGTH = 3;

/**
 * Extract significant keywords from text.
 * Filters out stop words, short words, and normalizes to lowercase.
 */
export function extractKeywords(text: string): Set<string> {
  const keywords = new Set<string>();

  // Split by non-word characters (keeps alphanumeric and hyphens)
  const words = text.toLowerCase().split(/[^a-z0-9-]+/);

  for (const word of words) {
    // Skip short words, stop words, and pure numbers
    if (word.length >= MIN_WORD_LENGTH && !STOP_WORDS.has(word) && !/^\d+$/.test(word)) {
      keywords.add(word);
    }
  }

  return keywords;
}

/**
 * Split text into segments, marking which segments are keyword matches.
 * Returns an array of { text, isMatch } objects for rendering.
 */
export function segmentTextByKeywords(
  text: string,
  keywords: Set<string>
): Array<{ text: string; isMatch: boolean }> {
  const segments: Array<{ text: string; isMatch: boolean }> = [];

  // Split into word and non-word segments while preserving the original text
  // Use the same character set as extractKeywords: letters, digits, and hyphens
  const parts = text.split(/([^a-zA-Z0-9-]+)/);

  for (const part of parts) {
    if (!part) continue;

    // Check if this part is a word (not just whitespace/punctuation)
    // Must match the same character set as extractKeywords
    const isWord = /^[a-zA-Z0-9-]+$/.test(part);

    if (isWord) {
      const cleanWord = part.toLowerCase().replace(/^-+|-+$/g, '');
      const isMatch = keywords.has(cleanWord);
      segments.push({ text: part, isMatch });
    } else {
      // Whitespace or punctuation - not a match
      segments.push({ text: part, isMatch: false });
    }
  }

  return segments;
}

/**
 * Calculate match statistics between resume text and JD keywords.
 */
export function calculateMatchStats(
  resumeText: string,
  jdKeywords: Set<string>
): {
  matchedKeywords: Set<string>;
  matchCount: number;
  totalKeywords: number;
  matchPercentage: number;
} {
  const resumeKeywords = extractKeywords(resumeText);
  const matchedKeywords = new Set<string>();

  for (const keyword of jdKeywords) {
    if (resumeKeywords.has(keyword)) {
      matchedKeywords.add(keyword);
    }
  }

  const matchCount = matchedKeywords.size;
  const totalKeywords = jdKeywords.size;
  const matchPercentage = totalKeywords > 0 ? Math.round((matchCount / totalKeywords) * 100) : 0;

  return { matchedKeywords, matchCount, totalKeywords, matchPercentage };
}

type ResumeKeywordBuckets = {
  summary: Set<string>;
  titles: Set<string>;
  skills: Set<string>;
  body: Set<string>;
};

function collectResumeKeywordBuckets(resumeData: ResumeData): ResumeKeywordBuckets {
  const summary = new Set<string>();
  const titles = new Set<string>();
  const skills = new Set<string>();
  const body = new Set<string>();

  const addTo = (bucket: Set<string>, text?: string | null) => {
    if (!text) return;
    for (const keyword of extractKeywords(text)) {
      bucket.add(keyword);
    }
  };

  addTo(summary, resumeData.summary);

  resumeData.workExperience?.forEach((exp) => {
    addTo(titles, exp.title);
    addTo(titles, exp.company);
    exp.description?.forEach((line) => addTo(body, line));
  });

  resumeData.education?.forEach((edu) => {
    addTo(titles, edu.degree);
    addTo(titles, edu.institution);
    addTo(body, edu.description);
  });

  resumeData.personalProjects?.forEach((project) => {
    addTo(titles, project.name);
    addTo(titles, project.role);
    addTo(body, project.github);
    addTo(body, project.website);
    project.description?.forEach((line) => addTo(body, line));
  });

  if (resumeData.additional) {
    resumeData.additional.technicalSkills?.forEach((item) => addTo(skills, item));
    resumeData.additional.certificationsTraining?.forEach((item) => addTo(skills, item));
    resumeData.additional.languages?.forEach((item) => addTo(body, item));
    resumeData.additional.awards?.forEach((item) => addTo(body, item));
  }

  return { summary, titles, skills, body };
}

/**
 * Approximate ATS-style score.
 *
 * This is intentionally more conservative than raw keyword overlap:
 * - skills/certifications carry the most weight
 * - summary and titles matter more than incidental mentions
 * - repeated evidence across sections improves confidence
 */
export function calculateAtsMatchStats(
  resumeData: ResumeData,
  jdKeywords: Set<string>
): {
  matchedKeywords: Set<string>;
  totalKeywords: number;
  atsScore: number;
} {
  const buckets = collectResumeKeywordBuckets(resumeData);
  let weightedScore = 0;
  const matchedKeywords = new Set<string>();

  for (const keyword of jdKeywords) {
    let coverage = 0;

    if (buckets.skills.has(keyword)) coverage += 0.45;
    if (buckets.summary.has(keyword)) coverage += 0.25;
    if (buckets.titles.has(keyword)) coverage += 0.2;
    if (buckets.body.has(keyword)) coverage += 0.15;

    const sectionHits = [
      buckets.skills.has(keyword),
      buckets.summary.has(keyword),
      buckets.titles.has(keyword),
      buckets.body.has(keyword),
    ].filter(Boolean).length;

    if (sectionHits >= 2) coverage += 0.1;
    if (coverage > 0) matchedKeywords.add(keyword);

    weightedScore += Math.min(coverage, 1);
  }

  const totalKeywords = jdKeywords.size;
  const atsScore = totalKeywords > 0 ? Math.round((weightedScore / totalKeywords) * 100) : 0;

  return { matchedKeywords, totalKeywords, atsScore };
}
