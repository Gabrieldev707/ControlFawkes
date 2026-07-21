import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WindowsVolumeControl } from './WindowsVolumeControl';

function renderControl(overrides: Partial<React.ComponentProps<typeof WindowsVolumeControl>> = {}) {
  const props = {
    volume: 45,
    isMuted: false,
    onSetVolume: vi.fn(),
    onStep: vi.fn(),
    onToggleMute: vi.fn(),
    onInteraction: vi.fn(),
    disabled: false,
    ...overrides,
  };
  render(<WindowsVolumeControl {...props} />);
  return props;
}

describe('WindowsVolumeControl', () => {
  it('mantém estado local durante o arraste e envia o valor final no pointerup', () => {
    const props = renderControl();
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '62' } });
    fireEvent.pointerUp(slider);

    expect(props.onSetVolume).toHaveBeenNthCalledWith(1, 62);
    expect(props.onSetVolume).toHaveBeenNthCalledWith(2, 62);
    expect((slider as HTMLInputElement).value).toBe('45');
    expect(screen.getByText('45%')).toBeTruthy();
  });

  it('sincroniza normalmente quando o VOLUME_STATE chega depois do rollback', () => {
    const props = {
      volume: 45,
      isMuted: false,
      onSetVolume: vi.fn(),
      onStep: vi.fn(),
      onToggleMute: vi.fn(),
    };
    const { rerender } = render(<WindowsVolumeControl {...props} />);
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '62' } });
    fireEvent.pointerUp(slider);
    rerender(<WindowsVolumeControl {...props} volume={62} />);

    expect((slider as HTMLInputElement).value).toBe('62');
  });

  it('envia cada mudança rápida, inclusive por teclado, e confirma o último valor', () => {
    const props = renderControl();
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.change(slider, { target: { value: '46' } });
    fireEvent.change(slider, { target: { value: '47' } });
    fireEvent.change(slider, { target: { value: '48' } });

    expect(props.onSetVolume).toHaveBeenCalledTimes(3);
    expect(props.onSetVolume).toHaveBeenNthCalledWith(1, 46);
    expect(props.onSetVolume).toHaveBeenNthCalledWith(2, 47);
    expect(props.onSetVolume).toHaveBeenLastCalledWith(48);
    expect(screen.getByText('48%')).toBeTruthy();
  });

  it('preserva o valor local no arraste e volta a sincronizar pela prop ao terminar', () => {
    const props = {
      volume: 45,
      isMuted: false,
      onSetVolume: vi.fn(),
      onStep: vi.fn(),
      onToggleMute: vi.fn(),
    };
    const { rerender } = render(<WindowsVolumeControl {...props} />);
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '62' } });
    rerender(<WindowsVolumeControl {...props} volume={30} />);
    expect((slider as HTMLInputElement).value).toBe('62');

    fireEvent.pointerUp(slider);
    rerender(<WindowsVolumeControl {...props} volume={30} />);
    expect((slider as HTMLInputElement).value).toBe('30');
  });

  it('envia passos exatamente tipados, respeita limites e usa o mudo real com SVG', () => {
    const props = renderControl({ isMuted: true });
    fireEvent.click(screen.getByRole('button', { name: 'Diminuir volume do computador' }));
    fireEvent.click(screen.getByRole('button', { name: 'Aumentar volume do computador' }));
    const mute = screen.getByRole('button', { name: 'Desativar mudo do computador' });
    fireEvent.click(mute);

    expect(props.onStep).toHaveBeenNthCalledWith(1, -5);
    expect(props.onStep).toHaveBeenNthCalledWith(2, 5);
    expect(props.onToggleMute).toHaveBeenCalledTimes(1);
    expect(mute.querySelector('svg')).toBeTruthy();
  });

  it('bloqueia passos que ultrapassariam 0 e 100', () => {
    const props = {
      volume: 0,
      isMuted: false,
      onSetVolume: vi.fn(),
      onStep: vi.fn(),
      onToggleMute: vi.fn(),
    };
    const { rerender } = render(<WindowsVolumeControl {...props} />);
    expect((screen.getByRole('button', { name: 'Diminuir volume do computador' }) as HTMLButtonElement).disabled).toBe(true);
    rerender(<WindowsVolumeControl {...props} volume={100} />);
    expect((screen.getByRole('button', { name: 'Aumentar volume do computador' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('aciona a interação no início, mudança, passo e mudo', () => {
    const props = renderControl();
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '50' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aumentar volume do computador' }));
    fireEvent.click(screen.getByRole('button', { name: 'Ativar mudo do computador' }));

    expect(props.onInteraction).toHaveBeenCalledTimes(4);
  });

  it('não chama nenhum callback quando indisponível', () => {
    const props = renderControl({ disabled: true });
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });
    const increase = screen.getByRole('button', { name: 'Aumentar volume do computador' });
    const mute = screen.getByRole('button', { name: 'Ativar mudo do computador' });

    expect((slider as HTMLInputElement).disabled).toBe(true);
    expect((increase as HTMLButtonElement).disabled).toBe(true);
    expect((mute as HTMLButtonElement).disabled).toBe(true);
    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '80' } });
    fireEvent.click(increase);
    fireEvent.click(mute);

    expect(props.onSetVolume).not.toHaveBeenCalled();
    expect(props.onStep).not.toHaveBeenCalled();
    expect(props.onToggleMute).not.toHaveBeenCalled();
    expect(props.onInteraction).not.toHaveBeenCalled();
  });

  it('envia o valor final também no cancelamento do ponteiro', () => {
    const props = renderControl();
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });
    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '73' } });
    fireEvent.pointerCancel(slider);
    expect(props.onSetVolume).toHaveBeenLastCalledWith(73);
    expect(props.onSetVolume).toHaveBeenCalledTimes(2);
  });

  it.each(['pointerUp', 'pointerCancel'] as const)(
    'não envia no %s se ficar indisponível durante o arraste e encerra no confirmado',
    (finishEvent) => {
      const props = {
        volume: 45,
        isMuted: false,
        onSetVolume: vi.fn(),
        onStep: vi.fn(),
        onToggleMute: vi.fn(),
        disabled: false,
      };
      const { rerender } = render(<WindowsVolumeControl {...props} />);
      const slider = screen.getByRole('slider', { name: 'Volume do computador' });

      fireEvent.pointerDown(slider);
      fireEvent.change(slider, { target: { value: '62' } });
      rerender(<WindowsVolumeControl {...props} disabled />);
      fireEvent[finishEvent](slider);

      expect(props.onSetVolume).toHaveBeenCalledTimes(1);
      expect(props.onSetVolume).toHaveBeenLastCalledWith(62);
      expect((slider as HTMLInputElement).value).toBe('45');

      rerender(<WindowsVolumeControl {...props} volume={30} />);
      expect((slider as HTMLInputElement).value).toBe('30');
    },
  );
});
