style:
	black --check -l 120 -N --diff `git ls-files "*.py"`
allstyle:
	black --check -l 120 -N --diff .
reformat:
	black -l 120 -N `git ls-files "*.py"`
allreformat:
	black -l 120 -N .
