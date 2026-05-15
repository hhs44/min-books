import { BaseAgent } from "./base.js";
import { countChapterLength } from "../utils/length-metrics.js";
import {
  buildShortHitDraftReviewSystemPrompt,
  buildShortHitDraftReviewUserPrompt,
  buildShortHitDraftRevisionFollowup,
  buildShortHitOutlineReviewSystemPrompt,
  buildShortHitOutlineReviewUserPrompt,
  buildShortHitOutlineRevisionFollowup,
  buildShortHitOutlineSystemPrompt,
  buildShortHitOutlineUserPrompt,
  buildShortHitPackageSystemPrompt,
  buildShortHitPackageUserPrompt,
  buildShortHitWriterSystemPrompt,
  buildShortHitWriterUserPrompt,
} from "../prompts/short-fiction.js";

export const SHORT_HIT_DEFAULT_CHAPTERS = 12;
export const SHORT_HIT_MIN_CHAPTERS = 12;
export const SHORT_HIT_MAX_CHAPTERS = 18;
export const SHORT_HIT_DEFAULT_CHARS_PER_CHAPTER = 1000;
export const SHORT_HIT_MIN_CHARS_PER_CHAPTER = 900;
export const SHORT_HIT_MAX_CHARS_PER_CHAPTER = 1200;

export interface ShortHitOutline {
  readonly storyTitle: string;
  readonly rawContent: string;
}

export interface ShortHitChapter {
  readonly number: number;
  readonly title: string;
  readonly content: string;
  readonly charCount: number;
}

export interface ShortHitBatchDraft {
  readonly storyTitle: string;
  readonly openingHook?: string;
  readonly chapters: ReadonlyArray<ShortHitChapter>;
  readonly rawContent: string;
}

export interface ShortHitSalesPackage {
  readonly title: string;
  readonly intro: string;
  readonly sellingPoints: ReadonlyArray<string>;
  readonly coverPrompt: string;
  readonly rawContent: string;
}

export interface ShortHitReference {
  readonly path?: string;
  readonly text: string;
}

export interface ShortHitOutlineInput {
  readonly direction: string;
  readonly chapterCount: number;
  readonly charsPerChapter: number;
  readonly reference?: ShortHitReference;
}

export interface ShortHitOutlineReviewInput {
  readonly direction: string;
  readonly outline: ShortHitOutline;
  readonly reference?: ShortHitReference;
}

export interface ShortHitOutlineRevisionInput extends ShortHitOutlineReviewInput {
  readonly review: string;
  readonly chapterCount: number;
  readonly charsPerChapter: number;
}

export interface ShortHitDraftInput {
  readonly direction: string;
  readonly outlineMarkdown: string;
  readonly chapterCount: number;
  readonly charsPerChapter: number;
}

export interface ShortHitDraftReviewInput extends ShortHitDraftInput {
  readonly draft: ShortHitBatchDraft;
}

export interface ShortHitDraftRevisionInput extends ShortHitDraftReviewInput {
  readonly review: string;
}

export interface ShortHitPackageInput {
  readonly direction: string;
  readonly outlineMarkdown: string;
  readonly draft: ShortHitBatchDraft;
}

export class ShortHitOutlineAgent extends BaseAgent {
  get name(): string {
    return "short-hit-outline";
  }

  async createOutline(input: ShortHitOutlineInput): Promise<ShortHitOutline> {
    const response = await retryShortHitCall(() =>
      this.chat([
        { role: "system", content: buildShortHitOutlineSystemPrompt() },
        { role: "user", content: buildShortHitOutlineUserPrompt(input) },
      ], { temperature: 0.55, maxTokens: 8192 }), this.name, this.log);

    return parseShortHitOutline(response.content);
  }
}

export class ShortHitOutlineReviewerAgent extends BaseAgent {
  get name(): string {
    return "short-hit-outline-reviewer";
  }

  async reviewOutline(input: ShortHitOutlineReviewInput): Promise<string> {
    const response = await retryShortHitCall(() =>
      this.chat([
        { role: "system", content: buildShortHitOutlineReviewSystemPrompt() },
        { role: "user", content: buildShortHitOutlineReviewUserPrompt(input) },
      ], { temperature: 0.3, maxTokens: 4096 }), this.name, this.log);

    return response.content.trim();
  }
}

export class ShortHitOutlineReviserAgent extends BaseAgent {
  get name(): string {
    return "short-hit-outline-reviser";
  }

  async reviseOutline(input: ShortHitOutlineRevisionInput): Promise<ShortHitOutline> {
    const response = await retryShortHitCall(() =>
      this.chat([
        { role: "system", content: buildShortHitOutlineSystemPrompt() },
        { role: "user", content: buildShortHitOutlineUserPrompt(input) },
        { role: "assistant", content: input.outline.rawContent.trim() },
        { role: "user", content: buildShortHitOutlineRevisionFollowup(input) },
      ], { temperature: 0.45, maxTokens: 8192 }), this.name, this.log);

    return parseShortHitOutline(response.content);
  }
}

export class ShortHitWriterAgent extends BaseAgent {
  get name(): string {
    return "short-hit-writer";
  }

  async writeDraft(input: ShortHitDraftInput): Promise<ShortHitBatchDraft> {
    const response = await retryShortHitCall(() =>
      this.chat([
        { role: "system", content: buildShortHitWriterSystemPrompt() },
        { role: "user", content: buildShortHitWriterUserPrompt(input) },
      ], {
        temperature: 0.58,
        maxTokens: estimateShortHitMaxTokens(input.chapterCount, input.charsPerChapter),
      }), this.name, this.log);

    return parseShortHitBatchDraft(response.content, { expectedChapters: input.chapterCount });
  }
}

export class ShortHitDraftReviewerAgent extends BaseAgent {
  get name(): string {
    return "short-hit-draft-reviewer";
  }

  async reviewDraft(input: ShortHitDraftReviewInput): Promise<string> {
    const response = await retryShortHitCall(() =>
      this.chat([
        { role: "system", content: buildShortHitDraftReviewSystemPrompt() },
        { role: "user", content: buildShortHitDraftReviewUserPrompt({
          ...input,
          draftMarkdown: renderShortHitDraftMarkdown(input.draft),
        }) },
      ], { temperature: 0.3, maxTokens: 8192 }), this.name, this.log);

    return response.content.trim();
  }
}

export class ShortHitDraftReviserAgent extends BaseAgent {
  get name(): string {
    return "short-hit-draft-reviser";
  }

  async reviseDraft(input: ShortHitDraftRevisionInput): Promise<ShortHitBatchDraft> {
    const response = await retryShortHitCall(() =>
      this.chat([
        { role: "system", content: buildShortHitWriterSystemPrompt() },
        { role: "user", content: buildShortHitWriterUserPrompt(input) },
        { role: "assistant", content: input.draft.rawContent.trim() || renderShortHitDraftMarkdown(input.draft) },
        { role: "user", content: buildShortHitDraftRevisionFollowup(input) },
      ], {
        temperature: 0.45,
        maxTokens: estimateShortHitMaxTokens(input.chapterCount, input.charsPerChapter),
      }), this.name, this.log);

    return parseShortHitBatchDraft(response.content, { expectedChapters: input.chapterCount });
  }
}

export class ShortHitPackagingAgent extends BaseAgent {
  get name(): string {
    return "short-hit-packaging";
  }

  async generatePackage(input: ShortHitPackageInput): Promise<ShortHitSalesPackage> {
    const response = await retryShortHitCall(() =>
      this.chat([
        { role: "system", content: buildShortHitPackageSystemPrompt() },
        { role: "user", content: buildShortHitPackageUserPrompt({
          direction: input.direction,
          outlineMarkdown: input.outlineMarkdown,
          draftMarkdown: renderShortHitDraftMarkdown(input.draft),
          draftTitle: input.draft.storyTitle,
        }) },
      ], { temperature: 0.45, maxTokens: 4096 }), this.name, this.log);

    return parseShortHitSalesPackage(response.content, input.draft.storyTitle);
  }
}

export function parseShortHitOutline(rawContent: string): ShortHitOutline {
  const storyTitle = normalizeTitle(
    extractTaggedBlock(rawContent, "SHORT_HIT_PLAN_TITLE")
    || extractTaggedBlock(rawContent, "SHORT_HIT_TITLE")
    || extractFirstHeading(rawContent)
    || "未命名短篇",
  ) || "未命名短篇";
  return { storyTitle, rawContent: rawContent.trim() };
}

export function parseShortHitBatchDraft(
  rawContent: string,
  options?: { readonly expectedChapters?: number },
): ShortHitBatchDraft {
  const expectedChapters = options?.expectedChapters ?? SHORT_HIT_DEFAULT_CHAPTERS;
  const storyTitle = normalizeTitle(
    extractTaggedBlock(rawContent, "SHORT_HIT_TITLE")
    || extractFirstHeading(rawContent)
    || "未命名短篇",
  ) || "未命名短篇";
  const openingHook = extractTaggedBlock(rawContent, "SHORT_HIT_OPENING_HOOK")
    || extractTaggedBlock(rawContent, "OPENING_HOOK");

  const chapters: ShortHitChapter[] = [];
  for (let number = 1; number <= expectedChapters; number += 1) {
    const title = normalizeChapterTitle(
      extractTaggedBlock(rawContent, `CHAPTER ${number} TITLE`)
      || extractMarkdownChapterTitle(rawContent, number)
      || `第${number}章`,
      number,
    );
    const content = sanitizeChapterContent(
      extractTaggedBlock(rawContent, `CHAPTER ${number} CONTENT`)
      || extractMarkdownChapterContent(rawContent, number)
      || "",
    );
    chapters.push({
      number,
      title,
      content,
      charCount: countChapterLength(content, "zh_chars"),
    });
  }

  return {
    storyTitle,
    openingHook: openingHook.trim() || undefined,
    chapters,
    rawContent,
  };
}

export function validateShortHitDraftForFinal(
  draft: ShortHitBatchDraft,
  options?: { readonly expectedChapters?: number },
): void {
  if (options?.expectedChapters !== undefined && draft.chapters.length !== options.expectedChapters) {
    throw new Error(`Short-hit draft is incomplete; expected ${options.expectedChapters} chapters, got ${draft.chapters.length}.`);
  }

  const emptyChapters = draft.chapters
    .filter((chapter) => !chapter.content.trim())
    .map((chapter) => chapter.number);
  if (emptyChapters.length > 0) {
    throw new Error(`Short-hit draft is incomplete; empty chapters: ${emptyChapters.join(", ")}.`);
  }
}

export function renderShortHitDraftMarkdown(draft: ShortHitBatchDraft): string {
  return [
    `# ${draft.storyTitle}`,
    draft.openingHook ? `## 开篇钩子\n\n${draft.openingHook}` : "",
    ...draft.chapters.map((chapter) => [
      `## ${formatShortHitChapterHeading(chapter.number, chapter.title)}`,
      "",
      chapter.content,
    ].join("\n")),
  ].filter(Boolean).join("\n\n");
}

export function parseShortHitSalesPackage(rawContent: string, fallbackTitle = "未命名短篇"): ShortHitSalesPackage {
  const title = normalizeTitle(
    extractTaggedBlock(rawContent, "SHORT_HIT_PACKAGE_TITLE")
    || extractTaggedBlock(rawContent, "SHORT_HIT_TITLE")
    || fallbackTitle,
  ) || fallbackTitle;
  const intro = extractTaggedBlock(rawContent, "SHORT_HIT_INTRO")
    || extractTaggedBlock(rawContent, "INTRO")
    || "";
  const sellingRaw = extractTaggedBlock(rawContent, "SHORT_HIT_SELLING_POINTS")
    || extractTaggedBlock(rawContent, "SELLING_POINTS")
    || "";
  const coverPrompt = extractTaggedBlock(rawContent, "SHORT_HIT_COVER_PROMPT")
    || extractTaggedBlock(rawContent, "COVER_PROMPT")
    || "";
  return {
    title,
    intro: intro.trim(),
    sellingPoints: sellingRaw
      .split(/\n+/)
      .map((line) => line.replace(/^\s*[-*]\s*/, "").trim())
      .filter(Boolean),
    coverPrompt: coverPrompt.trim(),
    rawContent: rawContent.trim(),
  };
}

function extractTaggedBlock(raw: string, tag: string): string {
  const escaped = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(
    `^\\s*===\\s*${escaped}\\s*===\\s*\\n([\\s\\S]*?)(?=^\\s*===\\s*[A-Z0-9_ ]+\\s*===\\s*$|(?![\\s\\S]))`,
    "im",
  );
  return pattern.exec(raw)?.[1]?.trim() ?? "";
}

function extractFirstHeading(raw: string): string {
  return raw.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? "";
}

function extractMarkdownChapterTitle(raw: string, number: number): string {
  const pattern = new RegExp(`^##\\s*(?:第\\s*${number}\\s*章\\s*)?(.+)$`, "m");
  return pattern.exec(raw)?.[1]?.trim() ?? "";
}

function extractMarkdownChapterContent(raw: string, number: number): string {
  const pattern = new RegExp(`^##\\s*(?:第\\s*${number}\\s*章\\s*)?.*$\\n([\\s\\S]*?)(?=^##\\s*(?:第\\s*${number + 1}\\s*章\\s*)?.*$|(?![\\s\\S]))`, "m");
  return pattern.exec(raw)?.[1]?.trim() ?? "";
}

function sanitizeChapterContent(raw: string): string {
  return raw
    .replace(/^```(?:md|markdown)?\s*/i, "")
    .replace(/```\s*$/i, "")
    .replace(/^===\s*[A-Z0-9_ ]+\s*===\s*$/gim, "")
    .trim();
}

function normalizeTitle(raw: string): string {
  return raw
    .split("\n")
    .map((line) => line.replace(/^#+\s*/, "").trim())
    .find(Boolean)
    ?.replace(/^《(.+)》$/, "$1")
    .trim() ?? "";
}

function normalizeChapterTitle(raw: string, number: number): string {
  const title = normalizeTitle(raw).replace(new RegExp(`^第\\s*${number}\\s*章\\s*`), "").trim();
  return title || `第${number}章`;
}

function formatShortHitChapterHeading(number: number, title: string): string {
  const trimmed = title.trim();
  if (!trimmed) return `第${number}章`;
  if (new RegExp(`^第\\s*${number}\\s*章`).test(trimmed)) return trimmed;
  return `第${number}章 ${trimmed}`;
}

function estimateShortHitMaxTokens(chapterCount: number, charsPerChapter: number): number {
  return Math.max(12_288, Math.ceil(chapterCount * charsPerChapter * 2.2) + 4096);
}

async function retryShortHitCall<T>(
  operation: () => Promise<T>,
  label: string,
  logger?: { warn(message: string): void },
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      return await operation();
    } catch (e) {
      lastError = e;
      if (attempt >= 2 || !isTransientShortHitError(e)) throw e;
      logger?.warn(`[${label}] transient LLM interruption, retrying once: ${String(e)}`);
    }
  }
  throw lastError;
}

function isTransientShortHitError(error: unknown): boolean {
  const message = String(error).toLowerCase();
  return message.includes("unexpected eof")
    || message.includes("econnreset")
    || message.includes("socket hang up")
    || message.includes("terminated")
    || message.includes("fetch failed");
}
