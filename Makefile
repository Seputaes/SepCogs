style:
	black --check -l 99 -N --diff `git ls-files "*.py"`
allstyle:
	black --check -l 99 -N --diff .
reformat:
	black -l 99 -N `git ls-files "*.py"`
allreformat:
	black -l 99 -N .
