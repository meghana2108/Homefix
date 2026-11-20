import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HomeFixEvent } from "../contract";
import { newTurn, reduce } from "../state/reduce";
import { EvidencePack } from "./EvidencePack";
import { TurnView } from "./TurnView";

const FINAL = { type: "final", answer: "", modality: "homefix", question_type: "manual_lookup", latency_ms: 900, profile: "lite", model: "m" };
const turn = ([
  { type: "token", text: "The washer can't drain. Clean the pump filter." },
  { type: "citation", quote: "E21 - The washer cannot drain the water.", page: 2, source: "apartment_guide_unit_4b.pdf", score: 100 },
  FINAL,
] as HomeFixEvent[]).reduce(reduce, newTurn("My washer shows E21", ["washer.jpg"]));
const photo = new File(["abc"], "washer.jpg", { type: "image/jpeg" });
const ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

describe("repair request", () => {
  it("every finished answer offers one", () => {
    const onEvidence = vi.fn();
    render(<TurnView turn={turn} onEvidence={onEvidence} />);
    fireEvent.click(screen.getByRole("button", { name: "Make a repair request" }));
    expect(onEvidence).toHaveBeenCalled();
  });

  it("shows the date, the file's fingerprint, the verified quote, the danger check and a letter", async () => {
    render(<EvidencePack turn={turn} files={[photo]} onClose={() => {}} />);
    const dialog = screen.getByRole("dialog", { name: "Repair request" });
    await waitFor(() => expect(screen.getByText(`SHA-256 ${ABC}`)).toBeInTheDocument());
    expect(dialog).toHaveTextContent("Nothing was uploaded");
    expect(screen.getByText("Word for word from apartment_guide_unit_4b.pdf, page 2")).toBeInTheDocument();
    expect(screen.getByText("E21 - The washer cannot drain the water.")).toBeInTheDocument();
    expect(screen.getByText(/nothing dangerous/)).toBeInTheDocument();
    expect((screen.getByLabelText("Letter to your landlord") as HTMLTextAreaElement).value).toMatch(/^Dear landlord,/);
  });

  it("editing the letter changes the pack fingerprint", async () => {
    render(<EvidencePack turn={turn} files={[photo]} onClose={() => {}} />);
    const fp = () => screen.getByText(/^Pack fingerprint/).textContent ?? "";
    await waitFor(() => expect(fp()).toMatch(/[0-9a-f]{64}$/));
    const before = fp();
    fireEvent.change(screen.getByLabelText("Letter to your landlord"), { target: { value: "Dear landlord, please fix it." } });
    await waitFor(() => expect(fp()).not.toBe(before));
  });

  it("prints, and closes with Escape", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    const onClose = vi.fn();
    render(<EvidencePack turn={turn} files={[photo]} onClose={onClose} />);
    await waitFor(() => screen.getByRole("button", { name: /Print or save as PDF/ }));
    fireEvent.click(screen.getByRole("button", { name: /Print or save as PDF/ }));
    expect(print).toHaveBeenCalled();
    expect(document.documentElement).toHaveClass("evidence-open");  // print shows only the sheet
    await act(async () => { fireEvent.keyDown(window, { key: "Escape" }); });
    expect(onClose).toHaveBeenCalled();
  });
});
