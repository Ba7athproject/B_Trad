import torch
print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))
