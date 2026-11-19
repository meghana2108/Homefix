import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";
import { MicButton } from "./MicButton";

class FakeWS {
  static last: FakeWS;
  static OPEN = 1;
  readyState = 0;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  binaryType = "blob";
  constructor(public url: string) { FakeWS.last = this; }
  send(d: unknown) { this.sent.push(d); }
  close() { this.readyState = 3; }
  open() { this.readyState = 1; this.onopen?.(); }
  server(msg: object) { this.onmessage?.({ data: JSON.stringify(msg) }); }
}

class FakeRecorder {
  static last: FakeRecorder;
  static isTypeSupported = () => true;
  state = "inactive";
  timeslice = 0;
  mimeType = "audio/webm;codecs=opus";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  constructor(public stream: unknown) { FakeRecorder.last = this; }
  start(t: number) { this.state = "recording"; this.timeslice = t; }
  stop() { this.state = "inactive"; this.chunk("last"); this.onstop?.(); }
  chunk(s: string) { this.ondataavailable?.({ data: new Blob([s]) }); }
}

const track = { stop: vi.fn() };
let getUserMedia: ReturnType<typeof vi.fn>;

beforeEach(() => {
  getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [track] });
  vi.stubGlobal("WebSocket", FakeWS);
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
});
afterEach(() => vi.unstubAllGlobals());

async function startRecording() {
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Start the mic" })); });
  await act(async () => { FakeWS.last.open(); });
}

describe("MicButton", () => {
  it("streams 3 s chunks, shows partials, and hands over only the final text", async () => {
    const onPartial = vi.fn();
    const onFinal = vi.fn();
    render(<MicButton onPartial={onPartial} onFinal={onFinal} />);
    await startRecording();
    expect(FakeWS.last.url).toMatch(/^ws:\/\/127\.0\.0\.1:8000\/api\/mic$/);
    expect(FakeRecorder.last.timeslice).toBe(3000);
    act(() => FakeRecorder.last.chunk("a"));
    expect(FakeWS.last.sent).toHaveLength(1);
    act(() => FakeWS.last.server({ type: "partial", text: "testing" }));
    expect(onPartial).toHaveBeenLastCalledWith("testing");

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Stop the mic" })); });
    expect(FakeWS.last.sent[FakeWS.last.sent.length - 1]).toBe(JSON.stringify({ type: "stop" }));
    expect(screen.getByRole("button", { name: /Transcribing/ })).toBeDisabled();
    act(() => FakeWS.last.server({ type: "final", text: "testing one two" }));
    expect(onFinal).toHaveBeenCalledWith("testing one two");
    expect(track.stop).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Start the mic" })).toBeEnabled();
  });

  it("explains a denied permission", async () => {
    getUserMedia.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    render(<MicButton onPartial={() => {}} onFinal={() => {}} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Start the mic" })); });
    expect(screen.getByRole("alert")).toHaveTextContent("Allow the microphone");
  });

  it("shows a server error and stops", async () => {
    render(<MicButton onPartial={() => {}} onFinal={() => {}} />);
    await startRecording();
    act(() => FakeWS.last.server({ type: "error", message: "The whisper model isn't installed." }));
    expect(screen.getByRole("alert")).toHaveTextContent("The whisper model isn't installed.");
    expect(screen.getByRole("button", { name: "Start the mic" })).toBeEnabled();
  });

  it("says so when the socket drops before the final", async () => {
    render(<MicButton onPartial={() => {}} onFinal={() => {}} />);
    await startRecording();
    act(() => FakeWS.last.onclose?.());
    expect(screen.getByRole("alert")).toHaveTextContent("Can't reach the live mic");
  });

  it("can be cancelled while the permission prompt is still open", async () => {
    let grant: (s: unknown) => void = () => {};
    getUserMedia.mockReturnValue(new Promise((res) => { grant = res; }));
    render(<MicButton onPartial={() => {}} onFinal={() => {}} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Start the mic" })); });
    fireEvent.click(screen.getByRole("button", { name: "Cancel the mic" }));
    expect(screen.getByRole("button", { name: "Start the mic" })).toBeEnabled();
    const lateTrack = { stop: vi.fn() };
    await act(async () => { grant({ getTracks: () => [lateTrack] }); });
    expect(lateTrack.stop).toHaveBeenCalled();  // a late grant doesn't leave the mic on
  });

  it("is hidden where the browser has no mic support", () => {
    Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
    const { container } = render(<MicButton onPartial={() => {}} onFinal={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Composer with the mic", () => {
  it("puts the final text in the box (after what was typed) and never sends it", async () => {
    const onText = vi.fn();
    const onSend = vi.fn();
    render(<Composer text="My washer:" onText={onText} files={[]} onFiles={() => {}} onSend={onSend} busy={false} note={null} />);
    await startRecording();
    act(() => FakeWS.last.server({ type: "partial", text: "shows error" }));
    expect(screen.getByText("shows error")).toBeInTheDocument();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Stop the mic" })); });
    act(() => FakeWS.last.server({ type: "final", text: "shows error E21" }));
    expect(onText).toHaveBeenCalledWith("My washer: shows error E21");
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.queryByText("shows error")).toBeNull();
  });
});
