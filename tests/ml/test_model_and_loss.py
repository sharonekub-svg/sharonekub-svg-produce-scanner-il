import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("timm")

from ml.training.losses import set_valued_ce  # noqa: E402
from ml.training.model import MultiTaskProduceNet  # noqa: E402


def test_set_valued_ce_reduces_to_ce_and_ignores_unknown():
    logits = torch.tensor([[2.0, 0.0, -1.0], [0.0, 0.0, 0.0]])
    exact = torch.tensor([[True, False, False], [False, False, False]])
    ce = torch.nn.functional.cross_entropy(logits[:1], torch.tensor([0]))
    assert torch.allclose(set_valued_ce(logits, exact), ce)


def test_set_valued_ce_partial_label_is_marginal():
    logits = torch.tensor([[1.0, 1.0, -5.0]])
    both = torch.tensor([[True, True, False]])
    p = torch.softmax(logits, 1)[0]
    assert torch.allclose(set_valued_ce(logits, both), -torch.log(p[0] + p[1]))


def test_all_unknown_batch_gives_zero_with_grad():
    logits = torch.zeros(4, 3, requires_grad=True)
    loss = set_valued_ce(logits, torch.zeros(4, 3, dtype=torch.bool))
    loss.backward()
    assert loss.item() == 0.0


@pytest.mark.parametrize("mode", ["shared", "per_produce"])
def test_multitask_forward_shapes(mode):
    net = MultiTaskProduceNet("mobilenetv3_small_050", 23, 4, 3, 3, ripeness_mode=mode, pretrained=False).eval()
    x = torch.randn(2, 3, 128, 128)
    o = net(x, produce_idx=torch.tensor([3, -1]))
    assert o["produce"].shape == (2, 23) and o["ripeness"].shape == (2, 4)
    assert o["freshness"].shape == (2, 3) and o["visual_spoilage"].shape == (2, 3)


def test_tiny_overfit_with_partial_labels():
    torch.manual_seed(0)
    net = MultiTaskProduceNet("mobilenetv3_small_050", 3, 4, 3, 3, pretrained=False)
    x = torch.randn(8, 3, 96, 96)
    y = torch.zeros(8, 3, dtype=torch.bool)
    y[torch.arange(8), torch.arange(8) % 3] = True
    opt = torch.optim.Adam(net.parameters(), 3e-3)
    first = None
    for _ in range(40):
        loss = set_valued_ce(net(x)["produce"], y)
        first = first or loss.item()
        opt.zero_grad(); loss.backward(); opt.step()
    assert loss.item() < first * 0.5
