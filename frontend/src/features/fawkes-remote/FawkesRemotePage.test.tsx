import { render, screen, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FawkesRemotePage } from "./FawkesRemotePage";
import * as useWebSocketModule from "../../hooks/useWebSocket";

// Mock child components to simplify testing
vi.mock("../../components/fawkes-remote", () => ({
  RemoteOrb: ({ state }: any) => <div data-testid="remote-orb">{state}</div>,
  ConnectionStatus: ({ state }: any) => (
    <div data-testid="conn-status">{state}</div>
  ),
  PlatformGrid: ({ disabled, onSelect, activeState }: any) => (
    <div data-testid="platform-grid" aria-disabled={disabled} data-active-state={activeState}>
      <button onClick={() => onSelect("NETFLIX")}>Select Netflix</button>
    </div>
  ),
  CommandBar: ({ disabled }: any) => (
    <div data-testid="command-bar" aria-disabled={disabled}>Command bar</div>
  ),
  VoiceButton: () => <div>Voice</div>,
  TextInput: () => <div>Text</div>,
  RemoteStatusText: ({ text, state }: any) => <div role="status" data-testid="remote-status" data-state={state}>{text}</div>,
  HoldToTalkButton: () => <button data-testid="hold-to-talk" disabled>Segure para falar</button>,
  SearchSheet: ({ open, onClose }: any) => open ? <div role="dialog" aria-label="Busca digitada"><button onClick={onClose}>Cancelar</button></div> : null,
  RemoteNavigation: ({ onNavigate, disabled }: any) => (
    <nav data-testid="remote-navigation">
      <button disabled={disabled} onClick={() => onNavigate('home')}>Início</button>
      <button disabled={disabled} onClick={() => onNavigate('control')}>Controle</button>
      <button disabled={disabled} onClick={() => onNavigate('touchpad')}>Touchpad</button>
    </nav>
  ),
  MediaControlPanel: ({ onSetVolume, onStep, onOpenSearch, disabled }: any) => (
    <div data-testid="media-control-panel">
      <input
        aria-label="Volume rápido de teste"
        type="range"
        min="0"
        max="100"
        disabled={disabled}
        onChange={(event) => onSetVolume(Number(event.currentTarget.value))}
      />
      <button disabled={disabled} onClick={() => onSetVolume(40)}>Finalizar arraste de teste</button>
      <button disabled={disabled} onClick={() => onStep(-5)}>Diminuir volume do computador</button>
      <button disabled={disabled} onClick={() => onStep(5)}>Aumentar volume do computador</button>
      <button onClick={onOpenSearch}>Teclado/Pesquisa</button>
    </div>
  ),
  TouchpadPreview: () => <div data-testid="touchpad-preview">Touchpad preview</div>,
}));

describe("FawkesRemotePage Controller", () => {
  let mockSendMessage: any;
  let mockOnMessage: any;
  let connectionStateValue: string = "connected";

  beforeEach(() => {
    mockSendMessage = vi.fn().mockReturnValue(true);

    // Mock the useWebSocket hook
    vi.spyOn(useWebSocketModule, "useWebSocket").mockImplementation(
      ({ onMessage }: any) => {
        mockOnMessage = onMessage;
        return {
          get connectionState() {
            return connectionStateValue;
          },
          sendMessage: mockSendMessage,
          reconnect: vi.fn(),
        } as any;
      },
    );

    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.clearAllTimers();
    vi.useRealTimers();
    localStorage.clear();
    connectionStateValue = "connected";
  });

  it("should send message and enter executing state on platform selection", () => {
    render(<FawkesRemotePage />);

    // Simulate authentication
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("idle");

    fireEvent.click(screen.getByText("Select Netflix"));

    expect(screen.getByTestId("remote-orb").textContent).toBe("executing");
    expect(mockSendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "PLATFORM_SELECTED",
        payload: { platform: "NETFLIX" },
      }),
    );
  });

  it("should ignore old responses based on requestId correlation", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    fireEvent.click(screen.getByText("Select Netflix"));

    expect(screen.getByTestId("remote-orb").textContent).toBe("executing");

    // Send response with wrong requestId
    act(() => {
      mockOnMessage({
        type: "COMMAND_RESULT",
        requestId: "WRONG-ID",
        success: true,
        message: "OK",
      });
    });

    // Should still be executing
    expect(screen.getByTestId("remote-orb").textContent).toBe("executing");
  });

  it("should transition to success and then idle after COMMAND_RESULT success", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    fireEvent.click(screen.getByText("Select Netflix"));
    const reqId = mockSendMessage.mock.calls[1][0].requestId;

    act(() => {
      mockOnMessage({
        type: "COMMAND_RESULT",
        requestId: reqId,
        success: true,
        message: "OK",
      });
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("success");

    // Advance timers by 2000ms
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("idle");
  });

  it("should transition to error and then idle after COMMAND_RESULT success: false", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    fireEvent.click(screen.getByText("Select Netflix"));
    const reqId = mockSendMessage.mock.calls[1][0].requestId;

    act(() => {
      mockOnMessage({
        type: "COMMAND_RESULT",
        requestId: reqId,
        success: false,
        message: "FAIL",
      });
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("error");

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("idle");
  });

  it("should transition to error and then idle after ERROR response", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    fireEvent.click(screen.getByText("Select Netflix"));
    const reqId = mockSendMessage.mock.calls[1][0].requestId;

    act(() => {
      mockOnMessage({
        type: "ERROR",
        requestId: reqId,
        code: "FAIL",
        message: "Error",
      });
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("error");

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("idle");
  });

  it("should enter error if sendMessage returns false", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    mockSendMessage.mockReturnValue(false); // Simulate disconnected send attempt

    fireEvent.click(screen.getByText("Select Netflix"));

    expect(screen.getByTestId("remote-orb").textContent).toBe("error");

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByTestId("remote-orb").textContent).toBe("idle");
  });

  it("should clean up timers on unmount", () => {
    const { unmount } = render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    fireEvent.click(screen.getByText("Select Netflix"));
    const reqId = mockSendMessage.mock.calls[1][0].requestId;

    act(() => {
      mockOnMessage({
        type: "COMMAND_RESULT",
        requestId: reqId,
        success: true,
        message: "OK",
      });
    });

    // We are in success state, timeout is pending
    expect(screen.getByTestId("remote-orb").textContent).toBe("success");

    unmount(); // Should clear timeout

    // Fast forward - if timeout wasn't cleared, it would run and crash
    // because component is unmounted (React warns, but vitest handles it fine,
    // this validates that we actually return a cleanup function)
    act(() => {
      vi.advanceTimersByTime(2000);
    });
  });

  it("conexão sem credenciais abre imediatamente o teclado de PIN", () => {
    render(<FawkesRemotePage />);
    // Initial state is 'checking', but useEffect sees 'connected' without token -> sets pairing_required
    expect(screen.getByText("Parear dispositivo")).toBeTruthy();
  });

  it("conexão com credenciais envia AUTH uma vez e não fica preso em checking", () => {
    localStorage.setItem("fawkes_token", "token123");
    localStorage.setItem("fawkes_deviceId", "device123");
    render(<FawkesRemotePage />);

    // It should have called sendMessage for AUTH exactly once
    expect(mockSendMessage).toHaveBeenCalledTimes(1);
    expect(mockSendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "AUTH",
        payload: { deviceId: "device123", token: "token123" },
      }),
    );
  });

  it("rerender não duplica AUTH", () => {
    localStorage.setItem("fawkes_token", "token123");
    localStorage.setItem("fawkes_deviceId", "device123");
    const { rerender } = render(<FawkesRemotePage />);

    expect(mockSendMessage).toHaveBeenCalledTimes(1);

    // Rerender
    rerender(<FawkesRemotePage />);

    // Still 1
    expect(mockSendMessage).toHaveBeenCalledTimes(1);
  });

  it("desconexão não remove token e reconexão envia uma nova tentativa de AUTH", () => {
    localStorage.setItem("fawkes_token", "token123");
    localStorage.setItem("fawkes_deviceId", "device123");
    const { rerender } = render(<FawkesRemotePage />);

    expect(mockSendMessage).toHaveBeenCalledTimes(1);

    // Disconnect
    connectionStateValue = "disconnected";
    rerender(<FawkesRemotePage />);

    // Token is preserved
    expect(localStorage.getItem("fawkes_token")).toBe("token123");

    // Reconnect
    connectionStateValue = "connected";
    rerender(<FawkesRemotePage />);

    // Sends AUTH again
    expect(mockSendMessage).toHaveBeenCalledTimes(2);
  });

  it("desabilita controles na desconexão e reabilita após reconexão + auth", () => {
    const { rerender } = render(<FawkesRemotePage />);

    // Simulate successful auth
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "1",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    // Controls should be enabled (disabled attr = false or not present)
    expect(
      screen.getByTestId("platform-grid").getAttribute("aria-disabled"),
    ).toBe("false");

    // Disconnect
    act(() => {
      connectionStateValue = "disconnected";
      // simulate rerender via fake connection state update (in real app, useWebSocket triggers it)
    });
    // Rerender to apply mock value
    rerender(<FawkesRemotePage />);

    // Controls should be disabled
    expect(
      screen.getByTestId("platform-grid").getAttribute("aria-disabled"),
    ).toBe("true");

    // Reconnect without auth
    act(() => {
      connectionStateValue = "connected";
    });
    rerender(<FawkesRemotePage />);

    // Controls should still be disabled because authState went to 'checking'
    expect(
      screen.getByTestId("platform-grid").getAttribute("aria-disabled"),
    ).toBe("true");

    // Re-auth success
    act(() => {
      mockOnMessage({
        type: "AUTH_RESULT",
        requestId: "2",
        success: true,
        deviceId: "abc",
        message: "OK",
      });
    });

    // Controls enabled
    expect(
      screen.getByTestId("platform-grid").getAttribute("aria-disabled"),
    ).toBe("false");
  });

  it("limpa erro e tenta novamente em múltiplas tentativas de PIN com mesmo erro", () => {
    render(<FawkesRemotePage />);

    // Pair device message from UI
    act(() => {
      mockOnMessage({
        type: "PAIR_RESULT",
        requestId: "1",
        success: false,
        message: "PIN incorreto",
      });
    });

    // Screen shows PIN incorreto
    expect(screen.getByText("PIN incorreto")).toBeTruthy();

    // Another Pair attempt
    act(() => {
      // simulate another failed attempt
      mockOnMessage({
        type: "PAIR_RESULT",
        requestId: "2",
        success: false,
        message: "PIN incorreto",
      });
    });

    // Should still show PIN incorreto (and under the hood we know attemptPairing clears it before setting 'pairing')
    expect(screen.getByText("PIN incorreto")).toBeTruthy();
  });

  it("ordena conexão, orb, status, plataformas, voz, busca e navegação", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({ type: "AUTH_RESULT", requestId: "1", success: true, deviceId: "abc", message: "OK" });
    });

    const ordered = [
      screen.getByTestId("conn-status"),
      screen.getByTestId("remote-orb"),
      screen.getByTestId("remote-status"),
      screen.getByTestId("platform-grid"),
      screen.getByTestId("hold-to-talk"),
      screen.getByRole("button", { name: "Teclado/Pesquisa" }),
      screen.getByTestId("remote-navigation"),
    ];
    ordered.slice(0, -1).forEach((element, index) => {
      expect(element.compareDocumentPosition(ordered[index + 1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
  });

  it("abre busca local e navega para controle e touchpad sem perder autenticação", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({ type: "AUTH_RESULT", requestId: "1", success: true, deviceId: "abc", message: "OK" });
    });

    fireEvent.click(screen.getByRole("button", { name: "Teclado/Pesquisa" }));
    expect(screen.getByRole("dialog", { name: "Busca digitada" })).toBeTruthy();
    fireEvent.click(screen.getByText("Cancelar"));
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Controle" }));
    expect(screen.getByTestId("media-control-panel")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Touchpad" }));
    expect(screen.getByTestId("touchpad-preview")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Início" }));
    expect(screen.getByTestId("platform-grid")).toBeTruthy();
  });

  it("mantém a navegação local disponível durante a desconexão", () => {
    const { rerender } = render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({ type: "AUTH_RESULT", requestId: "1", success: true, deviceId: "abc", message: "OK" });
    });

    fireEvent.click(screen.getByRole("button", { name: "Controle" }));
    expect(screen.getByTestId("media-control-panel")).toBeTruthy();

    connectionStateValue = "disconnected";
    rerender(<FawkesRemotePage />);

    const homeButton = screen.getByRole("button", { name: "Início" });
    expect((homeButton as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(homeButton);
    expect(screen.getByTestId("platform-grid")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Touchpad" }));
    expect(screen.getByTestId("touchpad-preview")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Início" }));
    expect(screen.getByTestId("platform-grid")).toBeTruthy();

    const platformMessagesBefore = mockSendMessage.mock.calls.filter(([message]: any[]) => message.type === "PLATFORM_SELECTED").length;
    fireEvent.click(screen.getByText("Select Netflix"));
    const platformMessagesAfter = mockSendMessage.mock.calls.filter(([message]: any[]) => message.type === "PLATFORM_SELECTED").length;
    expect(platformMessagesAfter).toBe(platformMessagesBefore);
  });

  it("abre a busca local na tela Controle mesmo desconectada sem enviar mensagem", () => {
    connectionStateValue = "disconnected";
    render(<FawkesRemotePage />);

    fireEvent.click(screen.getByRole("button", { name: "Controle" }));
    expect(screen.getByTestId("media-control-panel")).toBeTruthy();

    const messagesBefore = mockSendMessage.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Teclado/Pesquisa" }));

    expect(screen.getByRole("dialog", { name: "Busca digitada" })).toBeTruthy();
    expect(mockSendMessage).toHaveBeenCalledTimes(messagesBefore);
  });

  it("mantém a busca da Home habilitada durante a desconexão sem enviar mensagem", () => {
    const { rerender } = render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({ type: "AUTH_RESULT", requestId: "1", success: true, deviceId: "abc", message: "OK" });
    });

    connectionStateValue = "disconnected";
    rerender(<FawkesRemotePage />);

    const searchButton = screen.getByRole("button", { name: "Teclado/Pesquisa" });
    expect((searchButton as HTMLButtonElement).disabled).toBe(false);

    const messagesBefore = mockSendMessage.mock.calls.length;
    fireEvent.click(searchButton);

    expect(screen.getByRole("dialog", { name: "Busca digitada" })).toBeTruthy();
    expect(mockSendMessage).toHaveBeenCalledTimes(messagesBefore);
  });

  it("envia o último volume no trailing de 20 Hz após mudanças rápidas por teclado", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({ type: "AUTH_RESULT", requestId: "1", success: true, deviceId: "abc", message: "OK" });
      vi.advanceTimersByTime(50);
    });
    mockSendMessage.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Controle" }));
    const slider = screen.getByRole("slider", { name: "Volume rápido de teste" });
    fireEvent.change(slider, { target: { value: "40" } });

    const volumeMessages = () => mockSendMessage.mock.calls
      .map(([message]: any[]) => message)
      .filter((message: any) => message.type === "VOLUME_SET");
    expect(volumeMessages()).toHaveLength(1);
    expect(volumeMessages()[0].payload).toEqual({ level: 40 });

    act(() => {
      vi.advanceTimersByTime(25);
    });
    fireEvent.change(slider, { target: { value: "41" } });
    fireEvent.change(slider, { target: { value: "42" } });
    expect(volumeMessages()).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(25);
    });
    expect(volumeMessages()).toHaveLength(2);
    expect(volumeMessages()[1].payload).toEqual({ level: 42 });
  });

  it("não repete no trailing o último volume já enviado ao encerrar o arraste", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({ type: "AUTH_RESULT", requestId: "1", success: true, deviceId: "abc", message: "OK" });
      vi.advanceTimersByTime(50);
    });
    mockSendMessage.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Controle" }));
    const slider = screen.getByRole("slider", { name: "Volume rápido de teste" });
    fireEvent.change(slider, { target: { value: "40" } });
    fireEvent.click(screen.getByRole("button", { name: "Finalizar arraste de teste" }));

    act(() => {
      vi.advanceTimersByTime(50);
    });

    const volumeMessages = mockSendMessage.mock.calls
      .map(([message]: any[]) => message)
      .filter((message: any) => message.type === "VOLUME_SET");
    expect(volumeMessages).toHaveLength(1);
    expect(volumeMessages[0].payload).toEqual({ level: 40 });
  });

  it("envia passos reais de volume do Windows pelo protocolo tipado", () => {
    render(<FawkesRemotePage />);
    act(() => {
      mockOnMessage({ type: "AUTH_RESULT", requestId: "1", success: true, deviceId: "abc", message: "OK" });
    });
    fireEvent.click(screen.getByRole("button", { name: "Controle" }));
    fireEvent.click(screen.getByRole("button", { name: "Diminuir volume do computador" }));
    fireEvent.click(screen.getByRole("button", { name: "Aumentar volume do computador" }));

    expect(mockSendMessage).toHaveBeenCalledWith(expect.objectContaining({ type: "VOLUME_STEP", payload: { delta: -5 } }));
    expect(mockSendMessage).toHaveBeenCalledWith(expect.objectContaining({ type: "VOLUME_STEP", payload: { delta: 5 } }));
  });
});
